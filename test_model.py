#!/usr/bin/env python3
"""测试微调后的 Qwen2.5-0.5B + LoRA adapter 效果"""

import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

import torch, json, urllib.request
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from peft import PeftModel

print('下载 adapter 文件...')
os.makedirs('/tmp/adapter', exist_ok=True)
base = 'https://github.com/DTxiaweibing/TIMU/raw/main/adapter/'
for f in ['adapter_model.safetensors', 'adapter_config.json']:
    urllib.request.urlretrieve(base + f, f'/tmp/adapter/{f}')
    print(f'  {f} 下载完成')

print('加载 Qwen2.5-0.5B...')
model = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-0.5B', torch_dtype='auto', device_map='auto')
tokenizer = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B')

print('合并 LoRA adapter...')
model = PeftModel.from_pretrained(model, '/tmp/adapter').merge_and_unload()

pipe = pipeline('text-generation', model=model, tokenizer=tokenizer, max_new_tokens=256)

questions = [
    '虾塘氨氮突然升高到1.5mg/L怎么办？',
    '对虾早上吃料慢是什么原因？',
    '弧菌超标怎么处理？',
    '亚硝酸盐0.3mg/L怎么降？',
    '虾塘pH值偏高怎么办？',
]

for q in questions:
    r = pipe(messages=[{'role':'user', 'content':q}])
    print('='*60)
    print(f'Q: {q}')
    print(f'A: {r[0]["generated_text"][-1]["content"]}')

print('='*60)
print('测试完毕！')
