# Protocol Overview

The protocol involves three main components:
1. **User Station (US)**: Represents the end-user device.
2. **Base Message Station (BMS)**: Acts as an intermediary between the User Station and the Message Switching Centre.
3. **Message Switching Centre (MSC)**: Central server that handles authentication and message routing.

## Message Types

### Common Message Structure

All messages are JSON objects with a `type` field indicating the message type. Additional fields depend on the message type.

### User Station to BMS Messages

1. **Authentication Request**
   ```json
   {
       "type": "auth",
       "user_id": "<user_id>"
   }
   ```

2. **Authentication Response**
   ```json
   {
       "type": "auth_response",
       "user_id": "<user_id>",
       "challenge": "<challenge>",
       "response": "<response>"
   }
   ```

3. **Logout Request**
   ```json
   {
       "type": "auth_logout",
       "user_id": "<user_id>"
   }
   ```

4. **Text Message**
   ```json
   {
       "type": "text",
       "source_user": "<source_user_id>",
       "target_user": "<target_user_id>",
       "message": "<message>"
   }
   ```

### BMS to MSC Messages

1. **BMS Registration**
   ```json
   {
       "type": "bms_register",
       "bms_id": "<bms_id>"
   }
   ```

2. **Authentication Request Forward**
   ```json
   {
       "type": "auth",
       "user_id": "<user_id>",
       "bms_id": "<bms_id>"
   }
   ```

3. **Authentication Response Forward**
   ```json
   {
       "type": "auth_response",
       "user_id": "<user_id>",
       "challenge": "<challenge>",
       "response": "<response>"
   }
   ```

4. **Logout Request Forward**
   ```json
   {
       "type": "auth_logout",
       "user_id": "<user_id>",
       "bms_id": "<bms_id>"
   }
   ```

5. **Text Message Forward**
   ```json
   {
       "type": "text",
       "source_user": "<source_user_id>",
       "target_user": "<target_user_id>",
       "message": "<message>"
   }
   ```

### MSC to BMS Messages

1. **Challenge Message**
   ```json
   {
       "type": "challenge",
       "challenge": "<challenge>",
       "user_id": "<user_id>"
   }
   ```

2. **Authentication Result**
   ```json
   {
       "type": "auth_result",
       "status": "Authenticated" | "Failed",
       "user_id": "<user_id>"
   }
   ```

3. **Logout Result**
   ```json
   {
       "type": "logout_result",
       "status": "Logged out" | "Failed",
       "user_id": "<user_id>"
   }
   ```

4. **Text Message Forward**
   ```json
   {
       "type": "text",
       "source_user": "<source_user_id>",
       "target_user": "<target_user_id>",
       "message": "<message>"
   }
   ```

## Protocol Flow

1. **User Authentication**
   - User Station sends an `auth` message to BMS.
   - BMS forwards the `auth` message to MSC.
   - MSC generates a challenge and sends a `challenge` message to BMS.
   - BMS forwards the `challenge `message to User Station.
   - User Station responds with an `auth_response` message.
   - BMS forwards the `auth_response` message to MSC.
   - MSC validates the response and sends an `auth_response` message to BMS.
   - BMS forwards the `auth_response` message to User Station.

2. **User Logout**
   - User Station sends an `auth_logout` message to BMS.
   - BMS forwards the `auth_logout` message to MSC.
   - MSC processes the logout and sends a `logout_result` message to BMS.
   - BMS forwards the `logout_result` message to User Station.

3. **Text Messaging**
   - User Station sends a `text` message to BMS.
   - BMS forwards the `text` message to MSC.
   - MSC determines the target BMS and forwards the `text` message to the appropriate BMS.
   - Target BMS forwards the `text` message to the target User Station.
