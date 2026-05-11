def is_tls_client_hello(data: bytes):

    return (
        len(data) > 5 and
        data[0] == 0x16 and
        data[1] == 0x03
    )