#!/usr/bin/env python3
"""测试微调后的 Qwen2.5-0.5B 效果"""

import os, subprocess, sys
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

subprocess.run(['git', 'clone', '--depth', '1', 'https://github.com/DTxiaweibing/TIMU.git', '/tmp/TIMU'], check=True)
os.makedirs('/tmp/adapter', exist_ok=True)
for f in os.listdir('/tmp/TIMU/adapter'):
    os.system(f'cp /tmp/TIMU/adapter/{f} /tmp/adapter/{f}')

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

print('加载模型...')
model = AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-0.5B', torch_dtype='auto', device_map='auto')
tok = AutoTokenizer.from_pretrained('Qwen/Qwen2.5-0.5B')
model = PeftModel.from_pretrained(model, '/tmp/adapter').merge_and_unload()

questions = [
    '虾塘氨氮突然升高到1.5mg/L怎么办？',
    '对虾早上吃料慢是什么原因？',
    '弧菌超标怎么处理？',
    '亚硝酸盐0.3mg/L怎么降？',
    '虾塘pH值偏高怎么办？',
]

for q in questions:
    text = tok.apply_chat_template(
        [{'role':'system','content':'你是养虾专家'}, {'role':'user','content':q}],
        tokenize=False, add_generation_prompt=True)
    inputs = tok(text, return_tensors='pt').to(model.device)
    out = model.generate(**inputs, max_new_tokens=256, do_sample=True, temperature=0.7)
    ans = tok.decode(out[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)
    print(f'Q: {q}')
    print(f'A: {ans}')
    print()
