
import json
map_path = 'source_map.json'


class SourceContext:
    def __init__(self):
        self.map = json.load(open(map_path))

    def get_some_context(self, src, start, end, offset=50):
        if src not in self.map:
            return ''
        return self.__get_context_with_offset(self.map[src]['content'], start, end, offset)

    @staticmethod
    def __get_context_with_offset(content, start, end, offset):
        from_ = max((0, content.rfind('\n', 0, start+1)+1, start-offset))
        newline_ind = content.find('\n', end)
        if newline_ind != -1:
            to = min((len(content), newline_ind, end+offset))
        else:
            to = min(len(content), end+offset)
        result = content[from_:to].strip().replace('\n', ' ')
        if from_ == start-offset:
            result = '...'+result
        if to == end+offset:
            result += '...'
        return result

