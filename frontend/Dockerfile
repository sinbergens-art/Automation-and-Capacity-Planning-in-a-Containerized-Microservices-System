FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/nginx.conf

COPY index.html /usr/share/nginx/html/index.html
COPY app.js     /usr/share/nginx/html/app.js
COPY style.css  /usr/share/nginx/html/style.css
 
EXPOSE 80
 
HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1
 