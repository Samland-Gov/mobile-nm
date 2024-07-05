-- Create websocket connection
local ws = assert(http.websocket("ws://127.0.0.1:8080"))

-- Function to send a message and receive a response
local function send_and_receive(ws, message)
    ws.send(message)
    return ws.receive()
end

-- Open a TCP connection to example.com on port 80
local connect_message = {
    type = "tcp",
    data = {
        id = "example_tcp_connection",
        action = "connect",
        address = "example.com",
        port = 80
    }
}
ws.send(textutils.serializeJSON(connect_message))

-- Receive connect response
local connect_response = textutils.unserializeJSON(ws.receive())
print("Connect response:", textutils.serializeJSON(connect_response))

-- Send an HTTP GET request to example.com
local get_request_message = {
    type = "tcp",
    data = {
        id = "example_tcp_connection",
        action = "send",
        message = "GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n"
    }
}
ws.send(textutils.serializeJSON(get_request_message))

-- Receive and print HTTP response headers
local receive_message = {
    type = "tcp",
    data = {
        id = "example_tcp_connection",
        action = "receive"
    }
}
ws.send(textutils.serializeJSON(receive_message))
local http_response = textutils.unserializeJSON(ws.receive())
print("HTTP Response:", http_response.data)

-- Close the TCP connection
local close_message = {
    type = "tcp",
    data = {
        id = "example_tcp_connection",
        action = "close"
    }
}
ws.send(textutils.serializeJSON(close_message))

-- Receive close response
local close_response = textutils.unserializeJSON(ws.receive())
print("Close response:", textutils.serializeJSON(close_response))

-- Close websocket connection
ws.close()
