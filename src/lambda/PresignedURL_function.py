import json
import boto3
import uuid
import os
import urllib.parse
from botocore.config import Config
from botocore.exceptions import ClientError # 🚀 新增：用于捕获 DynamoDB 条件失败异常

# 强制使用 v4 签名
s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))

# 🚀 新增：初始化 DynamoDB 资源
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('YOUR_DYNAMODB_TABLE_NAME') # 替换为你的 DynamoDB 表名

def lambda_handler(event, context):
    bucket_name = os.environ['UPLOAD_BUCKET']
    
    # 统一提取 CORS 头，确保报错时前端也不会遇到跨域拦截
    cors_headers = {
        'Access-Control-Allow-Origin': '*', 
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'OPTIONS,POST'
    }
    
    # 处理 API Gateway 预检请求 (OPTIONS)
    if event.get('httpMethod') == 'OPTIONS':
        return {'statusCode': 200, 'headers': cors_headers, 'body': ''}

    try:
        body = json.loads(event.get('body', '{}'))
    except:
        body = {}
        
    # 接收前端参数
    target_lang = body.get('target_lang', 'zh').strip()
    email = body.get('email', 'shieliang22@gmail.com').strip()
    invite_code = body.get('invite_code', '').strip() # 🚀 新增：接收邀请码
    
    # 基础验证
    if not invite_code:
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({'error': 'Missing invite_code'})
        }

    # ==========================================
    # 🛡️ 核心防线：DynamoDB 原子计数与条件拦截
    # ==========================================
    try:
        table.update_item(
            Key={'invite_code': invite_code},
            UpdateExpression="SET CurrentUses = CurrentUses + :inc",
            ConditionExpression="CurrentUses < MaxUses",
            ExpressionAttributeValues={':inc': 1},
            ReturnValues="UPDATED_NEW"
        )
    except ClientError as e:
        # 如果次数满了，或者邀请码在数据库里根本不存在，会报这个错
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            print(f"[安全拦截] 邀请码 {invite_code} 已耗尽或不存在。")
            return {
                'statusCode': 403,
                'headers': cors_headers,
                'body': json.dumps({'error': '邀请码无效或已达到使用上限！'})
            }
        else:
            raise e # 抛出其他真实的数据库底层异常

    # ==========================================
    # 🚀 架构升级：直接将参数编入 S3 目录树中
    # ==========================================
    safe_email = urllib.parse.quote(email)
    file_key = f"uploads/{target_lang}/{safe_email}/{uuid.uuid4().hex[:8]}.mp4"
    
    try:
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': file_key,
                'ContentType': 'video/mp4'
            },
            ExpiresIn=300
        )
        
        print(f"[发证成功] 邀请码 {invite_code} 扣减完成，已下发通行证。")
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'upload_url': presigned_url,
                'file_key': file_key
            })
        }
    except Exception as e:
        return {
            'statusCode': 500, 
            'headers': cors_headers, 
            'body': json.dumps({'error': str(e)})
        }