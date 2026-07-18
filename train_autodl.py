#!/usr/bin/env python3
"""Qwen2.5-0.5B LoRA 微调 —— 用于 AutoDL / 任何 Linux GPU 环境"""

import os, json, requests, subprocess, sys, yaml

# 1. 装依赖（AutoDL 镜像自带 PyTorch，只需补几个包）
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q',
    'llama-factory', 'datasets', 'sentencepiece'])

# 2. 下载训练数据
url = 'https://raw.githubusercontent.com/DTxiaweibing/TIMU/main/kb_source/train_data.jsonl'
r = requests.get(url)
with open('train_data.jsonl', 'wb') as f:
    f.write(r.content)
count = sum(1 for _ in open('train_data.jsonl'))
with open('train_data.jsonl') as f:
    sample = json.loads(f.readline())
print(f'✅ 数据 {count} 条')

# 3. 注册数据集
ds_info = {'train_data': {'file_name': 'train_data.jsonl', 'formatting': 'sharegpt',
    'columns': {'messages': 'messages'}}}
with open('dataset_info.json', 'w') as f:
    json.dump(ds_info, f, ensure_ascii=False, indent=2)

# 4. 训练配置
config = {
    'model_name_or_path': 'Qwen/Qwen2.5-0.5B',
    'stage': 'sft', 'do_train': True,
    'finetuning_type': 'lora',
    'template': 'qwen', 'cutoff_len': 1024,
    'output_dir': '/root/output_qwen_timu',
    'overwrite_cache': True,
    'per_device_train_batch_size': 8,
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
    yaml.dump(config, f, allow_unicode=True)

os.environ['LLAMAFACTORY_DATASET_DIR'] = '.'

# 5. 开始训练
print('='*60)
print('🚀 开始训练... RTX 3090 约 20-30 分钟')
print('='*60)
subprocess.check_call(['llamafactory-cli', 'train', 'config/train.yaml'])

print('='*60)
print('✅ 训练完成！结果在 /root/output_qwen_timu/')
print('adapter_model.safetensors 即为 LoRA 权重')
print('='*60)
