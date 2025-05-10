# A wordpress tool

## Wordpress post to XHS image
```
python .\wp.py -h                  
usage: wp.py [-h] [--config CONFIG] [--wp_url WP_URL] [--wp_username WP_USERNAME] [--wp_password WP_PASSWORD] [--output_dir OUTPUT_DIR] [--title_font_size TITLE_FONT_SIZE]
             [--content_font_size CONTENT_FONT_SIZE] [--remove_images] [--width WIDTH] [--height HEIGHT]
             post

将WordPress文章转换为小红书图片

positional arguments:
  post                  文章ID或URL

options:
  -h, --help            show this help message and exit
  --config CONFIG       配置文件路径
  --wp_url WP_URL       WordPress URL
  --wp_username WP_USERNAME
                        WordPress用户名
  --wp_password WP_PASSWORD
                        WordPress密码
  --output_dir OUTPUT_DIR
                        图片输出目录
  --title_font_size TITLE_FONT_SIZE
                        标题字体大小
  --content_font_size CONTENT_FONT_SIZE
                        正文字体大小
  --remove_images       去掉原文中的图片
  --width WIDTH         图片宽度
  --height HEIGHT       图片高度
```
