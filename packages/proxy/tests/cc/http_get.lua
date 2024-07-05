-- Create websocket connection
local ws = assert(http.websocket("ws://127.0.0.1:8080"))

local function receive()
    -- Receive and print HTTP response headers
    local receive_message = {
        type = "tcp",
        data = {
            id = "example_tcp_connection",
            action = "receive"
        }
    }
    ws.send(textutils.serializeJSON(receive_message))
    data, binary = ws.receive()
    return textutils.unserializeJSON(data)
end

local function send(table)
    ws.send(textutils.serializeJSON(table))
    data, binary = ws.receive()
    return textutils.unserializeJSON(data)
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
local connect_response = send(connect_message)
print("Connect response:", connect_response.status)

-- Send an HTTP GET request to example.com
local get_request_message = {
    type = "tcp",
    data = {
        id = "example_tcp_connection",
        action = "send",
        message = "GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n"
    }
}
local get_response = send(get_request_message)
print("Get response:", get_response.status)


print("HTTP Response:")
while true do
    local r, b = ws.receive()
    local resp = textutils.unserializeJSON(r)
    if resp.status ~= nil and resp.status == "new_data" then
        print("Data:", resp.data)
    end
    -- print(resp.status)
    if resp.status ~= nil and resp.status == "disconnected" then
        break
    end
end


-- Close the TCP connection
local close_message = {
    type = "tcp",
    data = {
        id = "example_tcp_connection",
        action = "close"
    }
}
local close_response = send(close_message)

print("Close response:", close_response.status)

-- Close websocket connection
ws.close()
