#!/bin/sh
# 假 claude：回放采样文件，扮演 claude code（testing.md 第 6 层的进程边界 mock）。
# profile 的 command 形如 "fake_claude.sh /path/to/sample.jsonl"，
# 编排层还会追加 -p 等参数，故采样路径是 $1，其余参数忽略。
cat "$1"
