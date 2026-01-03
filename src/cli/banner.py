
import pyfiglet
from rich.console import Console
from rich.text import Text
from rich.padding import Padding

console = Console()

def interpolate_color(start_color, end_color, ratio):
    """计算颜色渐变"""
    r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
    g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
    b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
    return r, g, b

def print_banner():
    # 1. 字体生成
    try:
        f = pyfiglet.Figlet(font='ansi_shadow')
    except:
        f = pyfiglet.Figlet(font='slant')

    # 2. 生成文本 (不再需要拼接箭头)
    text_raw = f.renderText('CHAOS')
    
    # 过滤空行
    lines = [line for line in text_raw.splitlines() if line.strip()]
    if not lines: return

    # 3. 配色方案 (清冷蓝 -> 霓虹粉)
    COL_CYAN_BLUE = (0, 210, 255)   
    COL_HOT_PINK  = (255, 50, 180) 
    
    # 4. 像素纹理映射表
    # 将线性符号替换为块状阴影
    char_map = {
        '_': '░', 
        '|': '▒', 
        '/': '▒', 
        '\\': '▒', 
        ')': '▒', 
        '(': '▒', 
        '`': '░', 
        '.': '░',
        ',': '░'
    }

    gradient_text = Text()
    max_width = max(len(line) for line in lines)

    for line in lines:
        for i, char in enumerate(line):
            # A. 替换字符 (制造颗粒感)
            display_char = char_map.get(char, char)
            
            # B. 计算颜色
            ratio = i / max_width if max_width > 0 else 0
            r, g, b = interpolate_color(COL_CYAN_BLUE, COL_HOT_PINK, ratio)

            # C. 样式处理
            if char in char_map: 
                # 阴影部分：大幅压暗 (0.3)，制造深邃立体感
                r, g, b = int(r*0.3), int(g*0.3), int(b*0.3)
                style = f"rgb({r},{g},{b})"
            elif char.strip():
                # 实体部分：高亮加粗
                style = f"bold rgb({r},{g},{b})"
            else:
                style = None

            gradient_text.append(display_char, style=style)
        
        gradient_text.append("\n")

    # 5. 输出展示 (无边框，带一点上下间距)
    console.print(Padding(gradient_text, (1, 0, 0, 0)))

        # 辅助提示栏 (配色也进行呼应)
    console.print(f"Tips:")
    console.print(
        f"1.[white] 输入 [bold]exit[/] 退出 | [bold]Alt+Enter[/] 换行 | [bold]Enter[/] 提交[/]\n",
        justify="left"
    )