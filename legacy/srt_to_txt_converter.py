import os
import re

def srt_to_text(srt_content):
    # Remove timing lines and sequence numbers, keep text content
    text = re.sub(r'\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', srt_content)
    # Remove remaining sequence numbers and clean up
    text = re.sub(r'\d+(\n|$)', '', text)
    # Remove multiple newlines and trim
    text = re.sub(r'\n+', '\n', text).strip()
    return text

def convert_srt_to_txt(input_folder, output_folder=None):
    if output_folder is None:
        output_folder = input_folder
    elif not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(input_folder):
        if filename.endswith('.srt'):
            input_path = os.path.join(input_folder, filename)
            output_filename = os.path.splitext(filename)[0] + '.txt'
            output_path = os.path.join(output_folder, output_filename)

            try:
                # Read with UTF-8 encoding
                with open(input_path, 'r', encoding='utf-8') as srt_file:
                    srt_content = srt_file.read()
                
                converted_text = srt_to_text(srt_content)
                
                # Write with UTF-8 encoding
                with open(output_path, 'w', encoding='utf-8') as txt_file:
                    txt_file.write(converted_text)
                    
                print(f"Converted: {filename} -> {output_filename}")
                
            except UnicodeDecodeError:
                print(f"Error: Failed to decode {filename} as UTF-8. Trying with 'utf-8-sig'...")
                try:
                    with open(input_path, 'r', encoding='utf-8-sig') as srt_file:
                        srt_content = srt_file.read()
                    converted_text = srt_to_text(srt_content)
                    with open(output_path, 'w', encoding='utf-8') as txt_file:
                        txt_file.write(converted_text)
                    print(f"Converted: {filename} -> {output_filename} (using UTF-8-BOM)")
                except:
                    print(f"Error: Failed to convert {filename}")
            except Exception as e:
                print(f"Error converting {filename}: {str(e)}")

if __name__ == "__main__":
    input_dir = input("Enter input directory path: ").strip()
    output_dir = input("Enter output directory path (press Enter to use input directory): ").strip()
    
    if not output_dir:
        output_dir = None
        
    convert_srt_to_txt(input_dir, output_dir)