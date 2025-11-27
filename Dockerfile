FROM pandoc/latex:latest

# Install XeLaTeX and necessary packages for fonts
# texlive-xetex is needed for xelatex engine
# ttf-dejavu provides Unicode fonts with Cyrillic support
RUN apk add --no-cache \
    texlive-xetex \
    ttf-dejavu \
    ttf-liberation \
    font-noto

# Set working directory
WORKDIR /data

# Default command
ENTRYPOINT ["pandoc"]
