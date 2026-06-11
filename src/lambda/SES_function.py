import json
import boto3
from botocore.exceptions import ClientError

ses_client = boto3.client('ses')
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    print("接收到上游交棒的数据:", json.dumps(event))
    
    # ⚠️ 请在这里填入你刚刚验证通过的发件人邮箱！
    SENDER = "shieliang22@gmail.com" 
    
    # 收件人邮箱（测试阶段，前端传过来的也是你的这个邮箱）
    RECIPIENT = event.get('user_email')
    
    job_name = event.get('job_name', 'Unknown-Job')
    bucket = event.get('srt_bucket')
    srt_key = event.get('srt_key')
    
    # 巧妙提取语言代码 (例如从 Test-Job-009-zh.srt 中提取 zh)
    target_lang = srt_key.split('-')[-1].split('.')[0] if '-' in srt_key else 'en'
    
    # 1. 动态生成 S3 预签名安全下载链接 (有效期 24 小时 = 86400 秒)
    try:
        download_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket, 
                'Key': srt_key,
                'ResponseContentDisposition': f'attachment; filename="{srt_key}"' # 强制浏览器作为附件下载，并指定下载后的文件名
            },
            ExpiresIn=86400 
        )
    except Exception as e:
        print(f"生成下载链接失败: {e}")
        download_url = "#"

    SUBJECT = f"🎉 您的 AI 多语言字幕已全自动生成！ (任务: {job_name})"

    # 2. 注入硬核且高颜值的 HTML 响应式模板
    HTML_BODY = f"""
    <html>
    <head></head>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f4f7f6; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border-top: 6px solid #ff9900;">
            <div style="padding: 30px; text-align: center; background: #232f3e; color: white;">
                <h2 style="margin: 0; font-size: 24px;">Serverless AI Subtitle Pipeline</h2>
            </div>
            <div style="padding: 30px; color: #333333; line-height: 1.6;">
                <p style="font-size: 16px; font-weight: bold;">尊贵的研发工程师，您好：</p>
                <p>您提交的视频多语言字幕流水线任务已顺利完工！AI 已经完成了语音提取、智能断句以及跨语言翻译。</p>
                
                <table style="width: 100%; margin: 20px 0; border-collapse: collapse; background: #f9f9f9; border-radius: 4px;">
                    <tr>
                        <td style="padding: 12px; font-weight: bold; border-bottom: 1px solid #eeeeee;">任务标识:</td>
                        <td style="padding: 12px; border-bottom: 1px solid #eeeeee;">{job_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; font-weight: bold; border-bottom: 1px solid #eeeeee;">目标语言:</td>
                        <td style="padding: 12px; border-bottom: 1px solid #eeeeee;"><span style="background: #ff9900; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">{target_lang.upper()}</span></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; font-weight: bold;">存储位置:</td>
                        <td style="padding: 12px; color: #555;">s3://{bucket}/{srt_key}</td>
                    </tr>
                </table>
                
                <p style="margin-top: 30px; text-align: center;">
                    <a href="{download_url}" style="background-color: #ff9900; color: white; padding: 12px 30px; text-decoration: none; font-weight: bold; border-radius: 4px; display: inline-block; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">立即下载标准 SRT 字幕文件</a>
                </p>
                <p style="font-size: 12px; color: #999999; text-align: center; margin-top: 20px;">*温馨提示：该下载链接采用 AWS S3 预签名安全技术，有效期为 24 小时。</p>
            </div>
            <div style="background: #f4f7f6; padding: 15px; text-align: center; font-size: 12px; color: #666666; border-top: 1px solid #eeeeee;">
                由 AWS Step Functions & Amazon SES 全自动触发
            </div>
        </div>
    </body>
    </html>
    """

    # 3. 调用 SES 发送邮件
    try:
        response = ses_client.send_email(
            Destination={'ToAddresses': [RECIPIENT]},
            Message={
                'Body': {'Html': {'Charset': "UTF-8", 'Data': HTML_BODY}},
                'Subject': {'Charset': "UTF-8", 'Data': SUBJECT}
            },
            Source=SENDER
        )
    except ClientError as e:
        print("Amazon SES API 抛出异常:", e.response['Error']['Message'])
        return {"status": "FAILED", "error": e.response['Error']['Message']}
    else:
        print("邮件发送成功! Message ID:", response['MessageId'])
        return {"status": "NOTIFICATION_SENT", "message_id": response['MessageId']}