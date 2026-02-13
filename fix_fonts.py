# coding: utf-8
import sys

input_file = sys.argv[1]
with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ('name=', 'name='),
    ('Microsoft YaHei', 'Microsoft YaHei'),
    ('SimHei', 'SimHei'),
    ('SimSun', 'SimSun'),
    ('Arial', 'Arial'),
    ('Times New Roman', 'Times New Roman'),
    ('Courier New', 'Courier New'),
    ('supports_latin', 'supports_latin'),
    ('supports_chinese', 'supports_chinese'),
    ('supports_japanese', 'supports_japanese'),
    ('supports_korean', 'supports_korean'),
    ('type=', 'type='),
]

for bad, good in replacements:
    content = content.replace(bad, good)

output_file = input_file
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed')
