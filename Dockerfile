FROM pandoc/latex:latest

# Install XeLaTeX and necessary packages for fonts
# texlive-xetex is needed for xelatex engine
# ttf-dejavu provides Unicode fonts with Cyrillic support
RUN apk add --no-cache \
    ttf-dejavu \
    ttf-liberation \
    font-noto

# Add Russian support via tlmgr (correct for pandoc/latex image)
RUN tlmgr install collection-langcyrillic

# Set working directory
WORKDIR /data

# Default command
ENTRYPOINT ["pandoc"]
