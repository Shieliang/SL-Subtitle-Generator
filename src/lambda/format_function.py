import json
import boto3

s3_client = boto3.client('s3')

def format_time(seconds_str):
    sec = float(seconds_str)
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    secs = int(sec % 60)
    msecs = int(round((sec - int(sec)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"

def lambda_handler(event, context):
    # 智能识别上游：是直接过来的（未翻译），还是从翻译微服务交棒过来的（已翻译）
    is_translated = event.get('is_translated', False)
    
    job_name = event['job_name']
    target_lang = event.get('target_lang', 'zh')
    transcribe_output = event['transcribe_status']['TranscriptionJob']
    bucket_name = transcribe_output['Transcript']['TranscriptFileUri'].split('/')[-2]
    
    srt_key = f"{job_name}-{target_lang}.srt"
    srt_content = ""
    line_counter = 1

    print(f"【格式化微服务】启动。是否属于已翻译链路？ -> {is_translated}")

    if is_translated:
        # 【接口 A】处理来自翻译微服务的数据：直接读取已经翻译好的简化 segments
        json_key = event['translated_json_key']
        response = s3_client.get_object(Bucket=bucket_name, Key=json_key)
        data = json.loads(response['Body'].read().decode('utf-8'))
        
        for seg in data['segments']:
            start = format_time(seg['start_time'])
            end = format_time(seg['end_time'])
            srt_content += f"{line_counter}\n{start} --> {end}\n{seg['text']}\n\n"
            line_counter += 1
            
    else:
        # 【接口 B】处理来自直传无需翻译链路的数据：读取原始 Transcribe JSON 进行华语自适应断句
        json_key = f"{job_name}.json"
        response = s3_client.get_object(Bucket=bucket_name, Key=json_key)
        data = json.loads(response['Body'].read().decode('utf-8'))
        items = data['results']['items']
        
        current_line_words = []
        start_time = None
        detected_source_lang = transcribe_output.get('LanguageCode', 'en-US')
        is_asian_lang = detected_source_lang.startswith(('zh', 'ja'))
        MAX_WORDS = 5 if is_asian_lang else 8
        
        for item in items:
            content = item['alternatives'][0]['content']
            if item['type'] == 'punctuation':
                if current_line_words:
                    current_line_words[-1] += content
                continue
            if not start_time:
                start_time = format_time(item['start_time'])
            current_line_words.append(content)
            end_time = format_time(item['end_time'])
            
            if len(current_line_words) >= MAX_WORDS or content.endswith(('.', '?', '!', '。', '？', '！')):
                join_char = "" if is_asian_lang else " "
                sentence = join_char.join(current_line_words)
                srt_content += f"{line_counter}\n{start_time} --> {end_time}\n{sentence}\n\n"
                line_counter += 1
                current_line_words = []
                start_time = None

        if current_line_words:
            join_char = "" if is_asian_lang else " "
            sentence = join_char.join(current_line_words)
            srt_content += f"{line_counter}\n{start_time} --> {end_time}\n{sentence}\n\n"

    # 3. 统一写回 S3
    print(f"正在将解耦重构后的字幕写入 S3: {srt_key}")
    s3_client.put_object(
        Bucket=bucket_name,
        Key=srt_key,
        Body=srt_content.encode('utf-8'),
        ContentType='text/plain; charset=utf-8'
    )
    
    return {
        "status": "SUCCESS",
        "srt_bucket": bucket_name,
        "srt_key": srt_key,
        "job_name": job_name,
        "user_email": event.get('email', '')
    }