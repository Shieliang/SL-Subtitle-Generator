import json
import boto3
import urllib.parse

sfn_client = boto3.client('stepfunctions')

def lambda_handler(event, context):
    STATE_MACHINE_ARN = "arn:aws:states:us-east-1:987762561422:stateMachine:SL-Subtitle-Generator-Step-Function" 
    
    for record in event['Records']:
        try:
            body = json.loads(record['body'])
            
            if 'Records' in body and len(body['Records']) > 0 and 's3' in body['Records'][0]:
                s3_info = body['Records'][0]['s3']
                bucket_name = s3_info['bucket']['name']
                
                # S3 原生发来的带双重编码的钥匙
                raw_key = s3_info['object']['key']
                # 完美解码出真实的物理钥匙
                object_key = urllib.parse.unquote_plus(raw_key)
                
                # 🚀 核心修复：这里必须用 object_key，千万不能用 raw_key！
                video_s3_uri = f"s3://{bucket_name}/{object_key}"
                
                parts = object_key.split('/')
                if len(parts) >= 4:
                    target_lang = parts[1]
                    email = urllib.parse.unquote(parts[2]) # 解码邮箱里的 @
                    file_id = parts[-1].split('.')[0]
                else:
                    target_lang = 'zh'
                    email = 'shieliang22@gmail.com'
                    file_id = 'unknown'
                
                job_name = f"Web-{target_lang}-{file_id}"
                print(f"【路径解析成功】目标语言: {target_lang} | 接收邮箱: {email}")

            else:
                job_name = body.get('job_name', 'ManualTest')
                video_s3_uri = body.get('video_s3_uri')
                target_lang = body.get('target_lang', 'zh')
                email = body.get('email', 'shieliang22@gmail.com')

            sfn_input = {
                "job_name": job_name,
                "video_s3_uri": video_s3_uri,
                "target_lang": target_lang,
                "email": email
            }
            
            response = sfn_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=f"E2E-{job_name}", 
                input=json.dumps(sfn_input)
            )
            print(f"🎉 状态机已激活! Execution ARN: {response['executionArn']}")
            
        except Exception as e:
            print(f"❌ 解析失败: {str(e)}")
            raise e
            
    return {"status": "SUCCESS"}