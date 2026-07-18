#!/usr/bin/env python3
"""Qwen2.5-0.5B LoRA 微调 —— 纯 transformers + peft + trl"""

import os, json, requests, subprocess, sys

subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'transformers>=4.45', 'peft', 'trl', 'datasets', 'sentencepiece'])

url = 'https://raw.githubusercontent.com/DTxiaweibing/TIMU/main/kb_source/train_data.jsonl'
r = requests.get(url)
with open('train_data.jsonl', 'wb') as f:
    f.write(r.content)
data = [json.loads(l) for l in open('train_data.jsonl')]
print(f'数据 {len(data)} 条')

from datasets import Dataset
def convert(examples):
    text = ''
    for msg in examples['messages']:
        role, content = msg['role'], msg['content']
        text += f'<|im_start|>{role}\n{content}<|im_end|>\n'
    text += '<|im_start|>assistant\n'
    return {'text': text}

ds = Dataset.from_list(data).map(convert)

from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer

model_name = 'Qwen/Qwen2.5-0.5B'
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype='auto', device_map='auto')
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.padding_side = 'right'

lora_config = LoraConfig(
    r=8, lora_alpha=16, target_modules=['q_proj','k_proj','v_proj','o_proj'],
    lora_dropout=0.1, bias='none', task_type='CAUSAL_LM')

model = get_peft_model(model, lora_config)
print(f'可训练参数: {model.num_parameters(only_trainable=True):,}')

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

trainer = SFTTrainer(
    model=model, args=args, train_dataset=ds,
    tokenizer=tokenizer, max_seq_length=1024)

print('开始训练...')
trainer.train()

model.save_pretrained('/root/timu_output/adapter')
tokenizer.save_pretrained('/root/timu_output/adapter')
print(f'完成！LoRA 权重在 /root/timu_output/adapter/adapter_model.safetensors')
