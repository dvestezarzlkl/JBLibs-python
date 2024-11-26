TXT_DISABLED   = "/DIS/"
TXT_ESC_isExit = "ESC - Exit"
TXT_SEL_INFO   = "Press next key to select: {c}\n (or press ENTER to select or BACKSPACE to delete last character)"
TXT_INVALID_TYPE_IN_LIS = "Invalid type in list"
TXT_RPT_CHCS  = "Repeated choice"
TXT_ERR       = "ERROR"
TXT_NFO       = "Info"
TXT_PRESS_KEY = "Press key to select ..."
TXT_SELECT    = "Select: {c}"
TXT_BACK      = "Back"
TXT_QUIT      = "Quit"
TXT_ABORTED   = "Aborted"
TXT_ERROR_OCCURRED = "Error occurred"
TXT_CMENU_ERR01 = "Script error, the number on the left and right does not match"
TXT_CMENU_ERR02 = "Script error, tuple expected"
TXT_CMENU_ERR03 = "Script error, incorrect spaceBetweenTexts setting: {tx}"
TXT_CMENU_ERR04 = "Unsupported type of print item"
TXT_CMENU_ERR05 = "Unsupported type of print item, expected c_menu_block_items"
TXT_CMENU_ERR06 = "Menu items must be a list or tuple"
TXT_CMENU_ERR07 = "Item of menu items must be instance of c_menu_item"
TXT_CMENU_ERR08 = "Menu width must be an integer, either 0 or in the range 20-100"
TXT_CMENU_ERR09 = "esc_is_quit must be a boolean"
TXT_CMENU_ERR10 = "qitEnabled must be a boolean"
TXT_CMENU_ERR11 = "{co} must be a string or instance of c_menu_block_items"

TXT_INPUT_A     = "Input"
TXT_INPUT_NEW_PWD = "New password"
TXT_END         = "End"

TXT_HLPR_STATUS_RUNNING = "RUNNING"
TXT_HLPR_STATUS_STPDIS = "STOPPED AND DISABLED"
TXT_HLPR_STATUS_STPENA = "STOPPED AND ENABLED"
TXT_HLPR_STATUS_NM_EMP = "Service name is empty"
TXT_HLPR_STATUS_ERR="Error getting service status"
TXT_HLPR_MUST_BE_ROOT="This script must be run as root."

TXT_INPUT_ERR = "Input too short, min 1 character"
TXT_LEN_ERR = "Input too long, max {maxLen} characters"

TXT_INPUT_YES = "Yes"
TXT_INPUT_NO = "No"
TXT_INPUT_RETURNKEY = "Press RETURN to continue ..."
TXT_INPUT_ANYKEY = "Press any key to continue ..."
TXT_INPUT_USERNAME = "Enter username: "
TXT_INPUT_PWD = "Enter a password"
TXT_INPUT_PWD_AGAIN = "AGAIN to confirm"
TXT_INPUT_PORT = "Enter a port"
TXT_SSMD_PORT_REANGE = "10000-65000"

TXT_C_UNIT_servNameType = "Invalid 'service_name' parameter type."
TXT_C_UNIT_servUnitType = "Service unit type mismatch."
TXT_C_UNIT_servDotErr = "Service name must contain at most one dot."
TXT_C_UNIT_servAtErr = "Service_name must not contain '@'; the template is specified by a parameter."
TXT_C_UNIT_servTmplNameErr = "Template name must not contain '@' or a dot."

TXT_C_UNIT_badCStatus = "Parameter status must be instance of c_unit_status"

TXT_SSMD_ERR01 = "The input string is empty. Expected format is like '100ms', '1m 30sec'."
TXT_SSMD_ERR02 = "Invalid part of input: '{tx}'. Expected format is like '100ms'."
TXT_SSMD_ERR03 = "Unknown unit: '{tx}'."
TXT_SSMD_ERR04 = "Time must be a non-negative number."
TXT_SSMD_ERR05 = "Invalid key type '{tx}'"
TXT_SSMD_ERR06 = "Invalid value type for key '{tx}'"
TXT_SSMD_ERR07 = "Source file not specified"
TXT_SSMD_ERR08 = "Service file already exists"
TXT_SSMD_ERR09 = "Source file does not exist"
TXT_SSMD_ERR10 = "Source file is missing"
TXT_SSMD_ERR11 = "Failed to create service"
TXT_SSMD_ERR12 = "Service file does not exist"
TXT_SSMD_ERR13 = "Failed to delete service"
TXT_SSMD_ERR14 = "Failed to stop service"
TXT_SSMD_ERR15 = "Error writing service file"
TXT_SSMD_ERR16 = "Error writing timer file"
TXT_SSMD_ERR17 = "Invalid username, only letters, digits, underscores, and hyphens are allowed"
TXT_SSMD_ERR18 = "Invalid input"
TXT_SSMD_ERR19 = "!!! Invalid password\nPassword must contain at least 8 characters, including letters, digits, and special characters"
TXT_SSMD_ERR20 = "Passwords do not match. Try again."
TXT_SSMD_ERR21 = "Invalid port. Must be between 10000-65000"

TXT_STATUS_ENA = "ENABLED"
TXT_STATUS_DIS = "DISABLED"
TXT_STATUS_RUN = "RUNNING"
TXT_STATUS_STP = "STOPPED"
TXT_STATUS_NEX = "NOT EXIST"

TXT_C_UNIT_noSystemd = "Systemd is not available on this system."

TXT_SELECT_TITLE = "Select an option"

TXT_SSH_MNG_001 = "Enter username"
TXT_SSH_MNG_002 = "User {name} already exists"
TXT_SSH_MNG_003 = "Creating user {name}"
TXT_SSH_MNG_004 = "User {name} created."
TXT_SSH_MNG_005 = "Enter password"
TXT_SSH_MNG_006 = "System user created"
TXT_SSH_MNG_007 = "Error repairing SSH directory for user"
TXT_SSH_MNG_008 = "SSH Manager directory is missing."
TXT_SSH_MNG_009 = "Certificate {key} already exists."
TXT_SSH_MNG_010 = "Enter certificate name"
TXT_SSH_MNG_011 = "Do you want to set a password for the certificate?"
TXT_SSH_MNG_012 = "Certificate created for user {name} with name {cert}."
TXT_SSH_MNG_013 = "Delete certificate {cert} from user {name}"
TXT_SSH_MNG_014 = "SSH Manager directory is missing."
TXT_SSH_MNG_015 = "Private key {key} does not exist."
TXT_SSH_MNG_016 = "Public key {key} does not exist."
TXT_SSH_MNG_017 = "Certificate {cert} deleted for user {name}."
TXT_SSH_MNG_018 = "Cannot delete certificate. See log for details."
TXT_SSH_MNG_019 = "Key already included."
TXT_SSH_MNG_020 = "SSH Manager directory is missing."
TXT_SSH_MNG_021 = "Public key {key_path} does not exist."
TXT_SSH_MNG_022 = "Key {key} added to authorized_keys for user {name}."
TXT_SSH_MNG_023 = "SSH Manager directory is missing."
TXT_SSH_MNG_024 = "Authorized keys file for user {name} does not exist."
TXT_SSH_MNG_025 = "Public key {pub} does not exist."
TXT_SSH_MNG_026 = "Key {key} removed from authorized_keys for user {name}."
TXT_SSH_MNG_027 = "Key {key} not found in authorized_keys for user {name}."
TXT_SSH_MNG_028 = "SSH Manager directory for user {name} does not exist."
TXT_SSH_MNG_029 = "Public key {key_path} does not exist."
TXT_SSH_MNG_030 = "SSH Manager directory for user {name} does not exist."
TXT_SSH_MNG_031 = "Private key {key_path} does not exist."
TXT_SSH_MNG_032 = "Enter new password"
TXT_SSH_MNG_033 = "Password changed for user {name}."
TXT_SSH_MNG_034 = "Error changing password for user {name}: {e}"
