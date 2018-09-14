from pathlib import Path
import xml.etree.ElementTree as ET
source_path = Path('ltf')


class SourceContext:
    def __init__(self, doc_id):
        self.doc_id = doc_id
        self.filepath = source_path / (doc_id + '.ltf.xml')

    @staticmethod
    def get_some_context(src, start, end):
        context_extractor = SourceContext(src)
        if not context_extractor.filepath.is_file():
            return ''
        context_extractor.query_context(start, end)

    def query_context(self, start, end):
        tree = ET.parse(self.filepath)
        root = tree.getroot()
        texts = []
        for child in root.findall('./DOC/TEXT/SEG'):
            seg_start, seg_end = int(child.get('start_char')), int(child.get('end_char'))
            if seg_end < start:
                continue
            if seg_start > end:
                break
            text = child.find('ORIGINAL_TEXT').text
            texts.append(text)
        return ' '.join(texts)

    def doc_exists(self):
        return self.filepath.is_file()


if __name__ == '__main__':
    sc = SourceContext('IC0014YP8')
    print(sc.filepath.is_file())
    print(sc.query_context(59, 75))
