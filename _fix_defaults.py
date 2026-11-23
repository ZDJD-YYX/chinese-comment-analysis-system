# -*- coding: utf-8 -*-
import io
p = r"e:\trae\中文评论智能分析系统\_build_dd.py"
s = io.open(p, encoding='utf-8').read()
s = s.replace("'CURRENT_TIMESTAMP'", "'系统时间'")
s = s.replace('"CURRENT_TIMESTAMP"', '"系统时间"')
s = s.replace("['salt', 'VARCHAR', '32', 'N', '—', \"''\", '盐值；BCrypt 模式留空']",
              "['salt', 'VARCHAR', '32', 'N', '—', '空串', '盐值；BCrypt 模式留空']")
io.open(p, 'w', encoding='utf-8').write(s)
print('replaced', s.count('系统时间'))
