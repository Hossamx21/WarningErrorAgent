CC=gcc
CFLAGS=-Wall -Wextra

all: app

app: main.o util.o extra.o
	$(CC) $(CFLAGS) -o app main.o util.o extra.o

main.o: main.c util.h extra.h
	$(CC) $(CFLAGS) -c main.c

util.o: util.c util.h
	$(CC) $(CFLAGS) -c util.c

extra.o: extra.c extra.h
	$(CC) $(CFLAGS) -c extra.c

clean:
	rm -f *.o app
