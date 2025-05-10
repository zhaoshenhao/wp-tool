import requests
import os
import yaml
import argparse
import re
from bs4 import BeautifulSoup
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import GetPosts, GetPost
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

class WordPressToXHS:
    def __init__(self, config):
        self.config = config
        self.file_counter = 0
        
        # 图片保存路径
        self.output_dir = config.get('output_dir', 'xhs_images')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # 字体设置
        try:
            font_path = config.get('font_path')
            title_size = config.get('title_font_size', 40)
            content_size = config.get('content_font_size', 30)
            
            if font_path:
                self.font_title = ImageFont.truetype(font_path, title_size)
                self.font_content = ImageFont.truetype(font_path, content_size)
            else:
                # 尝试常见Windows字体路径
                windows_fonts = [
                    "C:/Windows/Fonts/simhei.ttf",  # 黑体
                    "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
                    "C:/Windows/Fonts/simfang.ttf", # 仿宋
                    "C:/Windows/Fonts/simkai.ttf",  # 楷体
                    "C:/Windows/Fonts/simsun.ttc",  # 宋体
                ]
                
                for font in windows_fonts:
                    if os.path.exists(font):
                        self.font_title = ImageFont.truetype(font, title_size)
                        self.font_content = ImageFont.truetype(font, content_size)
                        break
                else:
                    # 如果都找不到，使用默认字体
                    self.font_title = ImageFont.load_default(size=title_size)
                    self.font_content = ImageFont.load_default(size=content_size)
                    
        except Exception as e:
            print(f"字体加载失败: {e}")
            self.font_title = ImageFont.load_default()
            self.font_content = ImageFont.load_default()
    
    def connect_wordpress(self):
        """连接到WordPress"""
        try:
            self.wp_client = Client(
                self.config['wp_url'],
                self.config['wp_username'],
                self.config['wp_password']
            )
            return True
        except Exception as e:
            print(f"连接WordPress失败: {e}")
            return False
    
    def get_post_by_id_or_url(self, post_id_or_url):
        """根据ID或URL获取单个博客文章"""
        if isinstance(post_id_or_url, int) or post_id_or_url.isdigit():
            # 通过ID获取文章
            post_id = int(post_id_or_url)
            post = self.wp_client.call(GetPost(post_id))
            return post
        else:
            # 通过URL获取文章（需要先获取所有文章进行匹配）
            posts = self.wp_client.call(GetPosts({'number': 100}))
            for post in posts:
                if post.link == post_id_or_url:
                    return post
            return None
    
    def download_image(self, url):
        """下载图片并返回PIL Image对象"""
        try:
            response = requests.get(url)
            img = Image.open(BytesIO(response.content))
            
            # 如果图片是RGBA模式，转换为RGB
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])  # 使用alpha通道作为mask
                img = background
            
            return img
        except Exception as e:
            print(f"下载图片失败: {e}")
            return None
    
    def remove_html_tags(self, text):
        """使用BeautifulSoup处理HTML"""
        soup = BeautifulSoup(text, 'html.parser')
        
        # 保留换行
        for br in soup.find_all('br'):
            br.replace_with('\n')
        
        # 转换格式标签
        for tag in soup.find_all(['strong', 'b']):
            tag.insert_before('*')
            tag.insert_after('*')
            tag.unwrap()
        
        for tag in soup.find_all(['em', 'i']):
            tag.insert_before('_')
            tag.insert_after('_')
            tag.unwrap()
        
        # 获取纯文本
        clean_text = soup.get_text(separator=' ')
        
        # 处理空白
        clean_text = re.sub(r'[ \t]+', ' ', clean_text)
        clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text)
        return clean_text.strip()
    
    def make_safe_filename(self, text):
        """生成安全的文件名"""
        import re
        text = re.sub(r'[\\/*?:"<>|]', "", text)  # 移除非法字符
        text = text.replace(" ", "_")  # 空格替换为下划线
        return text[:50]  # 限制长度
    
    def smart_text_wrap(self, text, font, max_width):
        """智能换行算法，改进的中英文分词和标点符号处理"""
        lines = []
        
        # 定义中英文标点符号（包括全角和半角）
        cjk_punctuation = '。，、；：？！「」『』（）《》【】…—～・'
        en_punctuation = ',.;:?!\'"()[]{}<>'
        all_punctuation = cjk_punctuation + en_punctuation
        
        # 按段落分割
        paragraphs = text.split('\n')
        
        for para in paragraphs:
            if not para.strip():
                lines.append('')
                continue
                
            # 初始化当前行
            current_line = []
            current_width = 0
            
            # 逐个字符处理，实现更精确的分词
            i = 0
            n = len(para)
            while i < n:
                char = para[i]
                
                # 处理中文及CJK字符（包括中文标点）
                if self.is_cjk_char(char) or char in cjk_punctuation:
                    # 中文单独成词
                    char_width = font.getlength(char)
                    
                    # 如果当前行放不下
                    if current_width + char_width > max_width:
                        if current_line:
                            lines.append(''.join(current_line))
                        current_line = [char]
                        current_width = char_width
                    else:
                        current_line.append(char)
                        current_width += char_width
                    i += 1
                    
                # 处理英文单词（包括数字和英文标点）
                else:
                    # 提取完整的英文单词（包括连字符和撇号）
                    word = []
                    while i < n and not (self.is_cjk_char(para[i]) or para[i] in cjk_punctuation):
                        word.append(para[i])
                        i += 1
                    word = ''.join(word)
                    
                    # 如果获取到内容
                    if word:
                        word_width = font.getlength(word)
                        
                        # 处理超长单词（如URL）
                        if word_width > max_width:
                            if current_line:
                                lines.append(''.join(current_line))
                                current_line = []
                                current_width = 0
                            
                            # 强制分割超长单词
                            for char in word:
                                char_width = font.getlength(char)
                                if current_width + char_width > max_width:
                                    lines.append(''.join(current_line))
                                    current_line = [char]
                                    current_width = char_width
                                else:
                                    current_line.append(char)
                                    current_width += char_width
                        else:
                            # 正常英文单词处理
                            if current_width + word_width > max_width:
                                if current_line:
                                    lines.append(''.join(current_line))
                                current_line = [word]
                                current_width = word_width
                            else:
                                current_line.append(word)
                                current_width += word_width
            
            # 添加最后一个段落
            if current_line:
                lines.append(''.join(current_line))
        
        return lines

    def is_cjk_char(self, char):
        """判断是否为CJK字符（中日韩）"""
        cp = ord(char)
        return ((0x4E00 <= cp <= 0x9FFF) or  # 常用CJK字符
            (0x3400 <= cp <= 0x4DBF) or  # CJK扩展A
            (0x20000 <= cp <= 0x2A6DF) or  # CJK扩展B
            (0x2A700 <= cp <= 0x2B73F) or  # CJK扩展C
            (0x2B740 <= cp <= 0x2B81F) or  # CJK扩展D
            (0x2B820 <= cp <= 0x2CEAF) or  # CJK扩展E
            (0xF900 <= cp <= 0xFAFF) or  # CJK兼容字符
            (0x2F800 <= cp <= 0x2FA1F))  # CJK兼容扩展
    

    def process_post(self, post, width=800, height=1440):
        """处理文章并生成图片，严格保持原始顺序"""
        # 初始化参数
        width = self.config.get('image_width', width)
        height = self.config.get('image_height', height)
        bg_color = (255, 255, 255)
        text_color = (0, 0, 0)
        
        output_files = []
        content_parts = []

        # 1. 解析内容为顺序化的部件
        paragraphs = [p.strip() for p in post.content.split('\n') if p.strip()]
        for para in paragraphs:
            if '<img' in para and not self.config.get('remove_images', False):
                # 图片部件
                img_url = self.extract_image_url(para)
                content_parts.append({
                    'type': 'image',
                    'url': img_url
                })
            else:
                # 文本部件
                clean_text = self.remove_html_tags(para)
                if clean_text:
                    content_parts.append({
                        'type': 'text',
                        'content': clean_text
                    })

        # 2. 处理内容部件
        current_img = None
        draw = None
        y_pos = 20
        
        for part in content_parts:
            if part['type'] == 'image':
                # 保存当前文字图片
                if current_img and y_pos > 20:
                    output_files.append(self.save_content_image(
                        current_img, post.title))
                    current_img = None
                
                # 下载并保存原始图片
                img = self.download_image(part['url'])
                if img:
                    ext = os.path.splitext(part['url'])[1].split('?')[0].lower()
                    ext = ext if ext in ['.jpg', '.jpeg', '.png', '.gif'] else '.jpg'
                    output_files.append(self.save_original_image(
                        img, post.title, ext))
            else:
                # 处理文本内容
                if current_img is None:
                    current_img = Image.new("RGB", (width, height), bg_color)
                    draw = ImageDraw.Draw(current_img)
                    y_pos = 20
                
                # 智能换行
                lines = self.smart_text_wrap(part['content'], self.font_content, width-100)
                for line in lines:
                    if y_pos + self.font_content.size > height:
                        output_files.append(self.save_content_image(
                            current_img, post.title))
                        current_img = Image.new("RGB", (width, height), bg_color)
                        draw = ImageDraw.Draw(current_img)
                        y_pos = 20
                    
                    draw.text((50, y_pos), line, fill=text_color, font=self.font_content)
                    y_pos += self.font_content.size + 10
        
        # 保存最后一张文字图片
        if current_img and y_pos > 20:
            output_files.append(self.save_content_image(
                current_img, post.title))

        return output_files

    def save_original_image(self, img, title, ext):
        """保存原始图片不修改"""
        self.file_counter += 1
        safe_title = self.make_safe_filename(title)
        filename = f"{safe_title}_{self.file_counter}{ext}"
        output_path = os.path.join(self.output_dir, filename)
        
        # 保持原始格式和质量
        if ext.lower() in ['.png', '.gif']:
            img.save(output_path, format=ext[1:].upper())
        else:
            img.save(output_path, quality=100, subsampling=0)  # 最高质量JPEG
        
        return output_path

    def save_content_image(self, img, title):
        """保存生成的文字内容图片"""
        self.file_counter += 1
        safe_title = self.make_safe_filename(title)
        output_path = os.path.join(self.output_dir, f"{safe_title}_{self.file_counter}.jpg")
        img.save(output_path, quality=95)
        return output_path
    
    def process_single_post(self, post_id_or_url):
        """处理单篇文章"""
        if not self.connect_wordpress():
            return None
        
        post = self.get_post_by_id_or_url(post_id_or_url)
        if not post:
            print(f"未找到文章: {post_id_or_url}")
            return None
        
        print(f"正在处理文章: {post.title}")
        try:
            output_paths = self.process_post(post)
            if output_paths:
                print("已生成图片:")
                for path in output_paths:
                    print(f"- {path}")
            return output_paths
        except Exception as e:
            print(f"处理文章 {post.title} 时出错: {e}")
            return None

    def extract_image_url(self, html):
        """从HTML中提取图片URL"""
        start = html.find('src="') + 5
        end = html.find('"', start)
        return html[start:end]

def load_config(config_path='config.yaml'):
    """加载配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"配置文件 {config_path} 不存在，使用默认配置")
        return {
            'wp_url': '',
            'wp_username': '',
            'wp_password': '',
            'output_dir': 'xhs_images',
            'title_font_size': 40,
            'content_font_size': 30,
            'remove_images': False
        }
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return None

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='将WordPress文章转换为小红书图片')
    parser.add_argument('post', help='文章ID或URL')
    parser.add_argument('--config', default='config.yaml', help='配置文件路径')
    parser.add_argument('--wp_url', help='WordPress URL')
    parser.add_argument('--wp_username', help='WordPress用户名')
    parser.add_argument('--wp_password', help='WordPress密码')
    parser.add_argument('--output_dir', help='图片输出目录')
    parser.add_argument('--title_font_size', type=int, help='标题字体大小')
    parser.add_argument('--content_font_size', type=int, help='正文字体大小')
    parser.add_argument('--remove_images', action='store_true', help='去掉原文中的图片')
    parser.add_argument('--width', help='图片宽度')
    parser.add_argument('--height', help='图片高度')
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    if config is None:
        return
    
    # 用命令行参数覆盖配置
    if args.wp_url: config['wp_url'] = args.wp_url
    if args.wp_username: config['wp_username'] = args.wp_username
    if args.wp_password: config['wp_password'] = args.wp_password
    if args.output_dir: config['output_dir'] = args.output_dir
    if args.title_font_size: config['title_font_size'] = args.title_font_size
    if args.content_font_size: config['content_font_size'] = args.content_font_size
    if args.output_dir: config['output_dir'] = args.output_dir
    if args.width: config;['image']['width'] = args.width
    if args.height: config;['image']['height'] = args.height
    if args.remove_images: config['remove_images'] = True
    
    # 检查必要配置
    if not config.get('wp_url') or not config.get('wp_username') or not config.get('wp_password'):
        print("错误: 必须提供WordPress URL、用户名和密码")
        return
    
    # 处理文章
    converter = WordPressToXHS(config)
    converter.process_single_post(args.post)

if __name__ == "__main__":
    main()