from html.parser import HTMLParser

class DivCounter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.div_stack = []

    def handle_starttag(self, tag, attrs):
        if tag == 'div':
            class_name = next((v for k, v in attrs if k == 'class'), 'no-class')
            id_name = next((v for k, v in attrs if k == 'id'), 'no-id')
            self.div_stack.append((class_name, id_name, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag == 'div':
            if self.div_stack:
                self.div_stack.pop()
            else:
                print(f"Extra closing div at line {self.getpos()[0]}")

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    parser = DivCounter()
    parser.feed(f.read())
    print("Unclosed divs:")
    for d in parser.div_stack:
        print(f"Line {d[2]}: class='{d[0]}', id='{d[1]}'")
