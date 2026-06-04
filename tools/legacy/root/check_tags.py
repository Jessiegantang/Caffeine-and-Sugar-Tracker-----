from html.parser import HTMLParser

class MyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        if tag in ['div', 'section', 'header', 'form', 'main', 'body', 'html']:
            self.tags.append(tag)

    def handle_endtag(self, tag):
        if tag in ['div', 'section', 'header', 'form', 'main', 'body', 'html']:
            if self.tags and self.tags[-1] == tag:
                self.tags.pop()
            else:
                print(f"Mismatched end tag: {tag}. Expected: {self.tags[-1] if self.tags else 'None'}")

with open(r'd:\AAAjessie\gugugu\Caffeine and Sugar Tracker - 备份\index.html', 'r', encoding='utf-8') as f:
    parser = MyHTMLParser()
    parser.feed(f.read())
    print("Unclosed tags remaining:", parser.tags)
