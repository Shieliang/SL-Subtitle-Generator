import json
import boto3

s3_client = boto3.client('s3')
translate_client = boto3.client('translate')

def lambda_handler(event, context):
    transcribe_output = event['transcribe_status']['TranscriptionJob']
    job_name = event['job_name']
    target_lang = event.get('target_lang', 'zh')
    detected_source_lang = transcribe_output.get('LanguageCode', 'en-US')
    
    bucket_name = transcribe_output['Transcript']['TranscriptFileUri'].split('/')[-2]
    json_key = f"{job_name}.json"
    
    # 翻译微服务产出的中间件 JSON 文件名
    output_json_key = f"{job_name}-translated-segments.json"
    
    print(f"【翻译微服务】正在读取原始数据: {json_key}，准备翻译至: {target_lang}")
    
    # 1. 从 S3 读取 Transcribe 的原始 JSON
    response = s3_client.get_object(Bucket=bucket_name, Key=json_key)
    data = json.loads(response['Body'].read().decode('utf-8'))
    items = data['results']['items']
    
    translated_segments = []
    current_line_words = []
    start_time = None
    MAX_WORDS = 8
    
    # 2. 核心翻译与断句映射逻辑
    for item in items:
        content = item['alternatives'][0]['content']
        if item['type'] == 'punctuation':
            if current_line_words:
                current_line_words[-1] += content
            continue
        if not start_time:
            start_time = item['start_time']
        current_line_words.append(content)
        end_time = item['end_time']
        
        if len(current_line_words) >= MAX_WORDS or content.endswith(('.', '?', '!')):
            english_sentence = " ".join(current_line_words)
            
            # 调用 AI 翻译
            translate_response = translate_client.translate_text(
                Text=english_sentence,
                SourceLanguageCode=detected_source_lang.split('-')[0],
                TargetLanguageCode=target_lang
            )
            
            # 存入简化版的带时间戳段落结构
            translated_segments.append({
                "start_time": start_time,
                "end_time": end_time,
                "text": translate_response['TranslatedText']
            })
            current_line_words = []
            start_time = None

    if current_line_words:
        english_sentence = " ".join(current_line_words)
        translate_response = translate_client.translate_text(
            Text=english_sentence,
            SourceLanguageCode=detected_source_lang.split('-')[0],
            TargetLanguageCode=target_lang
        )
        translated_segments.append({
            "start_time": start_time,
            "end_time": end_time,
            "text": translate_response['TranslatedText']
        })

    # 3. 将翻译好的简化段落结构写回 S3（不污染、不超重状态机 Payload）
    s3_client.put_object(
        Bucket=bucket_name,
        Key=output_json_key,
        Body=json.dumps({"segments": translated_segments}, ensure_ascii=False).encode('utf-8'),
        ContentType='application/json'
    )
    
    # 4. 完美交棒：告诉状态机“我已经翻译好了，文件在 S3 里，请让格式化微服务接手”
    return {
        "job_name": job_name,
        "target_lang": target_lang,
        "email": event.get('email', ''),
        "transcribe_status": event['transcribe_status'],
        "is_translated": True,             # 核心身份标签：标记此数据已被翻译
        "translated_json_key": output_json_key
    }