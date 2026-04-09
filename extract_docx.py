import sys
import zipfile
import xml.etree.ElementTree as ET
import os

# Set output to utf-8
sys.stdout.reconfigure(encoding='utf-8')

def get_docx_text(path):
    """
    Take the path of a docx file, return the text in it.
    """
    try:
        with zipfile.ZipFile(path) as z:
            xml_content = z.read('word/document.xml')
        
        tree = ET.fromstring(xml_content)
        
        # Namespaces
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        paragraphs = []
        for paragraph in tree.findall('.//w:p', ns):
            texts = [node.text for node in paragraph.findall('.//w:t', ns) if node.text]
            if texts:
                paragraphs.append("".join(texts))
        
        return "\n".join(paragraphs)
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    path = r"D:\posture_alarm\姿態警報系統報告書_v2.docx"
    if os.path.exists(path):
        print(get_docx_text(path))
    else:
        print(f"File not found: {path}")
