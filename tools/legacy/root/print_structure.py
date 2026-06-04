from html.parser import HTMLParser

class StructurePrinter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.indent = 0
        self.output = []

    def handle_starttag(self, tag, attrs):
        if tag in ['div', 'section']:
            class_name = next((v for k, v in attrs if k == 'class'), '')
            id_name = next((v for k, v in attrs if k == 'id'), '')
            self.output.append(f"{'  ' * self.indent}<{tag} id='{id_name}' class='{class_name}'>")
            self.indent += 1

    def handle_endtag(self, tag):
        if tag in ['div', 'section']:
            self.indent -= 1
            self.output.append(f"{'  ' * self.indent}</{tag}>")

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    parser = StructurePrinter()
    parser.feed(f.read())
    print('\n'.join(parser.output[:50]))
    print("...")
    print('\n'.join(parser.output[-30:]))
