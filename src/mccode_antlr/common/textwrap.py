def pre_mid_post(string, open_token, close_token):
    io = string.find(open_token)
    ic = string.rfind(close_token)
    if 0 < io < ic:
        return string[:io], string[io+1:ic], string[ic+1:]
    return None, string, None


class BaseWrapper:

    def __init__(self, hider: str = None, hidden: str = None, width: int = 80):
        self.hider = hider or 'hider'
        self.hidden = hidden or 'hidden'
        self.width = width

    @staticmethod
    def wrap(text: str, pad: str = None) -> list[str]:
        raise NotImplementedError

    @staticmethod
    def comment(name: str, content: str) -> str:
        raise NotImplementedError

    @staticmethod
    def start_block_comment(name: str) -> str:
        raise NotImplementedError

    @staticmethod
    def end_block_comment() -> str:
        raise NotImplementedError

    def block(self, name: str, content: str) -> str:
        raise NotImplementedError

    def line(self, name: str, items: list[str], sep: str = ' ') -> str:
        raise NotImplementedError

    def quoted_line(self, name: str, items: list[str], sep: str = ' ') -> str:
        raise NotImplementedError

    def lines(self, items: list[str]) -> str:
        raise NotImplementedError

    @staticmethod
    def metadata_group(name: str, mimetype: str, item: str, value: str) -> str:
        raise NotImplementedError

    @staticmethod
    def datatype(data_type: str) -> str:
        raise NotImplementedError

    @staticmethod
    def parameter(parameter: str) -> str:
        raise NotImplementedError

    @staticmethod
    def unit(unit: str) -> str:
        raise NotImplementedError

    @staticmethod
    def value(value: str) -> str:
        raise NotImplementedError

    @staticmethod
    def start_list(name: str) -> str:
        raise NotImplementedError

    @staticmethod
    def end_list(name: str) -> str:
        raise NotImplementedError

    @staticmethod
    def start_list_item() -> str:
        raise NotImplementedError

    @staticmethod
    def end_list_item() -> str:
        raise NotImplementedError

    @staticmethod
    def list_item(content: str) -> str:
        raise NotImplementedError

    @staticmethod
    def list_items(items: list[str]) -> str:
        raise NotImplementedError

    @staticmethod
    def escape(content: str) -> str:
        raise NotImplementedError

    @staticmethod
    def url(content: str) -> str:
        raise NotImplementedError

    @staticmethod
    def bold(content: str) -> str:
        raise NotImplementedError

    @staticmethod
    def emph(content: str) -> str:
        raise NotImplementedError

    @staticmethod
    def br() -> str:
        raise NotImplementedError

    @staticmethod
    def hide(content: str) -> str:
        raise NotImplementedError


class TextWrapper(BaseWrapper):

    def wrap(self, text: str, pad: str = None) -> list[str]:
        if pad is None:
            pad = ''
        return [self._wrap_line(line, self.width, pad) for line in text.splitlines(True)]

    def comment(self, name: str, content: str) -> str:
        pad = ' '*(len(name) + 1)
        lines = self.wrap(content, pad=pad)
        lines[0] = f'{name} {lines[0].strip()}'
        return '/*' + '\n* '.join(lines) + '\n*/'

    @staticmethod
    def start_block_comment(name: str) -> str:
        return f'/* {name}'

    @staticmethod
    def end_block_comment() -> str:
        return '*/'

    def block(self, name: str, content: str) -> str:
        return '\n'.join([name + '\n%{\n', content + '\n%}\n'])

    def line(self, name: str, items: list[str], sep: str = ' ') -> str:
        items = [item or 'None' for item in items]
        return '\n'.join(self.wrap(f'{name} {sep.join(items)}'))

    def quoted_line(self, name: str, items: list[str], sep: str = ' ') -> str:
        items = [item or 'None' for item in items]
        return '\n'.join(self.wrap(f'{name} "{sep.join(items)}"'))

    def lines(self, items: list[str]) -> str:
        return '\n'.join('\n'.join(self.wrap(line)) for line in items)

    @staticmethod
    def metadata_group(name: str, mimetype: str, item: str, value: str) -> str:
        return f'{name} "{mimetype}" {item} \n%{{\n{value}\n%}}\n'

    @staticmethod
    def datatype(data_type: str) -> str:
        return data_type

    @staticmethod
    def parameter(parameter: str) -> str:
        return f'{parameter}'

    @staticmethod
    def unit(unit: str) -> str:
        return f'/{unit}'

    @staticmethod
    def value(value: str) -> str:
        return f'{value}'

    @staticmethod
    def start_list(name: str) -> str:
        return name

    @staticmethod
    def end_list(name: str) -> str:
        return name

    @staticmethod
    def start_list_item() -> str:
        return ''

    @staticmethod
    def end_list_item() -> str:
        return ''

    @staticmethod
    def list_item(content: str) -> str:
        return content

    @staticmethod
    def list_items(items: list[str]) -> str:
        return '\n'.join([item for item in items])

    @staticmethod
    def escape(content: str) -> str:
        return content

    @staticmethod
    def url(content: str) -> str:
        return content

    @staticmethod
    def bold(content: str) -> str:
        return content

    @staticmethod
    def emph(content: str) -> str:
        return content

    @staticmethod
    def br() -> str:
        return ' '

    @staticmethod
    def hide(content: str) -> str:
        return content

    @staticmethod
    def _wrap_line(line, width, pad) -> str:
        # This is not good enough. TODO Use a combined McCode _and_ C parser to identify reasonable line break points
        return line


class HTMLWrapper(BaseWrapper):


    @staticmethod
    def wrap(text: str, pad: str = None) -> list[str]:
        return [text]

    @staticmethod
    def comment(name: str, content: str) -> str:
        return f"<details><summary>{name}</summary>{content}</details>"

    @staticmethod
    def start_block_comment(name: str) -> str:
        return f'<details><summary>{name}</summary>'

    @staticmethod
    def end_block_comment() -> str:
        return '</details>'

    def block(self, name: str, content: str) -> str:
        return '<br>'.join([self.bold(name) + ' %{' + self.hide(f'<pre>{content}</pre><br>') + '%} '])

    def line(self, name: str, items: list[str], sep: str = ' ') -> str:
        return ''.join(self.wrap(f'<b>{name}</b> {sep.join(items)}')) + '<br>'

    def quoted_line(self, name: str, items: list[str], sep: str = ' ') -> str:
        return ''.join(self.wrap(f'<b>{name}</b> "{sep.join(items)}"')) + '<br>'

    def lines(self, items: list[str]) -> str:
        return '<br>'.join('<br>'.join(self.wrap(line)) for line in items)

    def metadata_group(self, name: str, mimetype: str, item: str, value: str) -> str:
        return f'<b>{name}</b> <code>{mimetype}</code> <var>{item}</var>' + ' %{' + self.hide(f'<pre>{value}</pre>') +'%}'

    @staticmethod
    def datatype(data_type: str) -> str:
        return f'<code>{data_type}</code>'

    @staticmethod
    def parameter(parameter: str) -> str:
        return f'<var>{parameter}</var>'

    @staticmethod
    def unit(unit: str) -> str:
        return f'/{unit}'

    def value(self, value: str) -> str:
        return f'<code>{self.escape(str(value))}</code>'

    @staticmethod
    def start_list(name: str) -> str:
        return f'<ul> {name}'

    @staticmethod
    def end_list(name: str) -> str:
        return f'</ul> {name}'

    @staticmethod
    def start_list_item() -> str:
        return '<li>'

    @staticmethod
    def end_list_item() -> str:
        return '</li>'
    @staticmethod
    def list_item(content: str) -> str:
        return f'<li>{content}</li>'

    @staticmethod
    def list_items(items: list[str]) -> str:
        return ''.join([f'<li>{item}</li>' for item in items])

    @staticmethod
    def escape(content: str) -> str:
        from html import escape
        return escape(str(content))

    @staticmethod
    def url(content: str) -> str:
        return f'<a href="{content}">{content}</a>'

    @staticmethod
    def bold(content: str) -> str:
        return f'<b style="font-size:small">{content}</b>'

    @staticmethod
    def emph(content: str) -> str:
        return f'<em>{content}</em>'

    @staticmethod
    def br() -> str:
        return '<br>'

    def hide(self, content: str) -> str:
        from uuid import uuid4

        def span(c, tag, i, cont):
            return f'<span class="{c}" {tag}="{i}">{cont}</span>'

        if len(content.strip()):
            uuid = 'g-' + str(uuid4())  # a random UUID that _does not_ start with a 0
            return span(self.hider, 'data-id', uuid, span(self.hidden, 'id', uuid, content))

        return content
