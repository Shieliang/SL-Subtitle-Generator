import json
import boto3
import uuid
import os
import urllib.parse
from botocore.config import Config

# 强制使用 v4 签名
s3_client = boto3.client('s3', config=Config(signature_version='s3v4'))

def lambda_handler(event, context):
    bucket_name = os.environ['UPLOAD_BUCKET']
    try:
        body = json.loads(event.get('body', '{}'))
    except:
        body = {}
        
    # 接收参数
    target_lang = body.get('target_lang', 'zh').strip()
    email = body.get('email', 'shieliang22@gmail.com').strip()
    
    # 🚀 架构升级：直接将参数编入 S3 目录树中！丢弃可能含中文的原始文件名，改用纯净的 UUID
    # 格式变成: uploads/zh/shieliang22@gmail.com/1a2b3c4d.mp4
    safe_email = urllib.parse.quote(email) # 确保邮箱里的 @ 符号安全
    file_key = f"uploads/{target_lang}/{safe_email}/{uuid.uuid4().hex[:8]}.mp4"
    
    try:
        # 极其干净的签名参数！没有任何 Custom Metadata，S3 绝对不会拦！
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': file_key,
                'ContentType': 'video/mp4'
            },
            ExpiresIn=300
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*', 
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST'
            },
            'body': json.dumps({
                'upload_url': presigned_url,
                'file_key': file_key
            })
        }
    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}