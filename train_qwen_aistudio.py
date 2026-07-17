#!/usr/bin/env python3
"""Qwen2.5-0.5B LoRA 微调脚本 —— 用于百度 AI Studio / 任意 Linux 环境"""

import os, json, requests, subprocess, sys

# 1. 装依赖
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'transformers', 'datasets', 'accelerate', 'peft', 'trl', 'sentencepiece'])

# 2. 下载训练数据
url = 'https://raw.githubusercontent.com/DTxiaweibing/TIMU/main/kb_source/train_data.jsonl'
r = requests.get(url)
with open('train_data.jsonl', 'wb') as f:
    f.write(r.content)
count = sum(1 for _ in open('train_data.jsonl'))
with open('train_data.jsonl') as f:
    sample = json.loads(f.readline())
print(f'数据 {count} 条，样例：{json.dumps(sample, ensure_ascii=False)[:200]}')

# 3. 安装 LLaMA-Factory
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'llama-factory'])

# 4. 生成配置文件
config = {
    'model_name_or_path': 'Qwen/Qwen2.5-0.5B',
    'stage': 'sft', 'do_train': True,
    'finetuning_type': 'lora',
    'template': 'qwen', 'cutoff_len': 1024,
    'output_dir': 'output_qwen_timu',
    'overwrite_cache': True,
    'per_device_train_batch_size': 4,
    'gradient_accumulation_steps': 4,
    'lr_scheduler_type': 'cosine',
    'logging_steps': 10, 'save_steps': 200,
    'learning_rate': 5e-5, 'num_train_epochs': 3.0,
    'fp16': True, 'plot_loss': True,
    'lora_rank': 8, 'lora_alpha': 16, 'lora_dropout': 0.1,
    'lora_target': ['q_proj', 'k_proj', 'v_proj', 'o_proj'],
}

os.makedirs('config', exist_ok=True)
with open('config/train.yaml', 'w') as f:
    import yaml; yaml.dump(config, f, allow_unicode=True)

# 需要把数据注册到 dataset_info.json
ds_info = {'train_data': {'file_name': 'train_data.jsonl', 'formatting': 'sharegpt',
    'columns': {'messages': 'messages'}}}
with open('dataset_info.json', 'w') as f:
    json.dump(ds_info, f, ensure_ascii=False, indent=2)

# 5. 开始训练
print('='*60)
print('开始训练... 约 30-50 分钟')
print('='*60)
os.environ['LLAMAFACTORY_DATASET_DIR'] = '.'
subprocess.check_call(['llamafactory-cli', 'train', 'config/train.yaml'])

print('='*60)
print(f'训练完成！结果在 output_qwen_timu/')
print('adapter_model.safetensors 即为 LoRA 权重文件')
print('='*60)
