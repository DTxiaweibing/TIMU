#!/usr/bin/env python3
"""Qwen2.5-0.5B LoRA 微调 —— 直接用 transformers + peft，不用 LLaMA-Factory"""

import os, json, requests, subprocess, sys

# 1. 装基础包（PyTorch 已自带）
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'transformers>=4.45', 'peft', 'trl', 'datasets', 'sentencepiece'])

# 2. 下载数据
url = 'https://raw.githubusercontent.com/DTxiaweibing/TIMU/main/kb_source/train_data.jsonl'
r = requests.get(url)
with open('train_data.jsonl', 'wb') as f:
    f.write(r.content)
data = [json.loads(l) for l in open('train_data.jsonl')]
print(f'✅ 数据 {len(data)} 条')

# 3. 转为 ChatML 格式
from datasets import Dataset
def convert(examples):
    text = ''
    for msg in examples['messages']:
        role = msg['role']
        content = msg['content']
        if role == 'system':
            text += f'<|im_start|>system\n{content}<|im_end|>\n'
        elif role == 'user':
            text += f'<|im_start|>user\n{content}<|im_end|>\n'
        elif role == 'assistant':
            text += f'<|im_start|>assistant\n{content}<|im_end|>\n'
    text += '<|im_start|>assistant\n'
    return {'text': text}

ds = Dataset.from_list(data).map(convert)

# 4. 加载模型 + tokenizer
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer

model_name = 'Qwen/Qwen2.5-0.5B'
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype='auto', device_map='auto')
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.padding_side = 'right'

# 5. LoRA 配置
lora_config = LoraConfig(
    r=8, lora_alpha=16, target_modules=['q_proj','k_proj','v_proj','o_proj'],
    lora_dropout=0.1, bias='none', task_type='CAUSAL_LM')

model = get_peft_model(model, lora_config)
print(f'可训练参数: {model.num_parameters(only_trainable=True):,}')

# 6. 训练
args = TrainingArguments(
    output_dir='/root/timu_output',
    per_device_train_batch_size=8,
    gradient_accumulation_steps=2,
    num_train_epochs=3,
    learning_rate=5e-5,
    fp16=True,
    logging_steps=10,
    save_steps=200,
    lr_scheduler_type='cosine',
    report_to='none',
    save_only_model=True)

try:
    trainer = SFTTrainer(model=model, args=args, train_dataset=ds, tokenizer=tokenizer, max_seq_length=1024)
except TypeError:
    trainer = SFTTrainer(model=model, args=args, train_dataset=ds, processing_class=tokenizer, max_seq_length=1024)

print('='*60)
print('开始训练... RTX 5090 约 10 分钟')
print('='*60)
trainer.train()

# 7. 保存
model.save_pretrained('/root/timu_output/adapter')
tokenizer.save_pretrained('/root/timu_output/adapter')
print('='*60)
print(f'✅ 完成！LoRA 权重在 /root/timu_output/adapter/')
print('adapter_model.safetensors 下载到本地即可')
print('='*60)
