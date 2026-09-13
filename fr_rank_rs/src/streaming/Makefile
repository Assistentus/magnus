# Makefile
# ===================================================================
# Сборка C-примеров.
# ===================================================================

RUST_LIB = target/release/libmagnus.so
RUST_STATIC = target/release/libmagnus.a

# Для Linux
CC = gcc
CFLAGS = -Wall -O2 -I./include
LDFLAGS_DYNAMIC = -L./target/release -lmagnus -Wl,-rpath,./target/release
LDFLAGS_STATIC = $(RUST_STATIC) -lpthread -ldl -lm

# Для macOS
# RUST_LIB = target/release/libmagnus.dylib
# LDFLAGS_DYNAMIC = -L./target/release -lmagnus

all: rust examples

rust:
	cargo build --release --features streaming

examples: examples/use_from_c.c
	$(CC) $(CFLAGS) $< -o build/use_from_c $(LDFLAGS_DYNAMIC)

static: examples/use_from_c.c
	$(CC) $(CFLAGS) $< -o build/use_from_c_static $(LDFLAGS_STATIC)

clean:
	rm -rf build/* target/release/*.so target/release/*.a

.PHONY: all rust examples static clean