FROM alpine:latest

ENV TERM=xterm-256color

RUN apk update && apk add --no-cache \
    bash \
    abuild \
    build-base \
    git \
    curl \
    wget \
    ca-certificates \
    openssh-client \
    python3 \
    py3-pip \
    cmake \
    ninja \
    pkgconf \
    coreutils \
    util-linux \
    sudo \
    shadow

# Get the officiel key for Safecor repository
RUN curl -L -o /etc/apk/keys/safecor.rsa.pub https://alefbet.net/github/safecor/safecor.rsa.pub

# Update repositories list
RUN echo "https://alefbet.net/github/safecor" >> /etc/apk/repositories
RUN apk update 

# Create a build user
RUN useradd -G wheel,abuild -m -s /bin/bash builder

# Add user to sudoers
RUN echo "%wheel ALL=(ALL:ALL) NOPASSWD: ALL" > /etc/sudoers.d/wheel 
RUN chmod 0440 /etc/sudoers.d/wheel 
RUN chown root:root /etc/sudoers.d/wheel 

# Add the abuild public key
RUN mkdir -p /home/builder/.abuild
RUN chown builder:builder /home/builder/.abuild
RUN chmod 700 /home/builder/.abuild
COPY safecor.rsa.pub /home/builder/.abuild
RUN echo "PACKAGER_PRIVKEY=\"/home/builder/.abuild/safecor.rsa\"" > /home/builder/.abuild/abuild.conf
RUN chown builder:builder /home/builder/.abuild/*
RUN chmod 700 /home/builder/.abuild/*

# Set a login message for the private key
RUN echo "DON'T FORGET TO PUT THE PRIVATE KEY IN THE CONTAINER BEFORE USING ABUILD" > /etc/motd

USER builder 
WORKDIR /home/builder 

CMD ["/bin/bash"]