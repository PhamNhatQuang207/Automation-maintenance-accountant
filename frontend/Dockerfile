FROM nginx:alpine

# Copy cấu hình Nginx
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy các file tĩnh (CSS, JS, hình ảnh) để Nginx phục vụ trực tiếp
COPY frontend/static/ /usr/share/nginx/html/static/

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
