#!/bin/sh
# 带延时的假 claude：逐行回放采样（模拟真实流式输出），SSE 实时性测试用。
# 用法: fake_claude_slow.sh <sample.jsonl> [其余参数忽略]
while IFS= read -r line; do
  printf '%s\n' "$line"
  sleep 0.2
done < "$1"
