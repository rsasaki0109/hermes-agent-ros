# Lightweight status broadcast from the AgentNode on /hermes/agent_status.
uint8 IDLE=0
uint8 PLANNING=1
uint8 EXECUTING=2
uint8 WAITING_USER=3
uint8 ERROR=4

uint8 state
string current_call_id
string last_user_prompt
builtin_interfaces/Time stamp
