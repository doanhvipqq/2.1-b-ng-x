
with open('c:\\Users\\Administrator\\Downloads\\2.0-b-ng-main\\main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

cutoff_index = -1
for i, line in enumerate(lines):
    if 'application.run_polling()' in line:
        cutoff_index = i
        break

if cutoff_index != -1:
    clean_lines = lines[:cutoff_index+1]
    clean_lines.append('\n')
    clean_lines.append("if __name__ == '__main__':\n")
    clean_lines.append("    keep_alive()\n")
    clean_lines.append("    main()\n")
    
    with open('c:\\Users\\Administrator\\Downloads\\2.0-b-ng-main\\main.py', 'w', encoding='utf-8') as f:
        f.writelines(clean_lines)
    print(f"Cleaned main.py. New length: {len(clean_lines)} lines.")
else:
    print("Could not find cutoff point.")
