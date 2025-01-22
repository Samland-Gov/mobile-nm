from samcom.bms.core import main

if __name__ == "__main__":
    HOST = "localhost"
    PORT = 9001
    MSC_URL = "ws://localhost:9000"
    BMS_ID = "BMS1"
    main(HOST, PORT, MSC_URL, BMS_ID)
    