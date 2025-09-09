# SpaceTraders Agent Logic - Contract Fulfillment State Machine

## Overview

This document describes the logic for an autonomous SpaceTraders agent that continuously negotiates and fulfills contracts. The agent operates as a state machine, transitioning between different states based on current conditions and available resources.

## Core State Machine

### States

1. **INITIALIZE** - Agent startup and registration
2. **ASSESS_SITUATION** - Check agent status, credits, ships, and available contracts
3. **NEGOTIATE_CONTRACT** - Find and negotiate available contracts
4. **ACCEPT_CONTRACT** - Accept the most profitable/feasible contract
5. **PLAN_FULFILLMENT** - Analyze contract requirements and plan execution
6. **ACQUIRE_RESOURCES** - Purchase ships or cargo space if needed
7. **EXECUTE_CONTRACT** - Navigate to required locations and fulfill contract terms
8. **DELIVER_GOODS** - Complete contract delivery requirements
9. **COMPLETE_CONTRACT** - Finalize contract and collect rewards
10. **EVALUATE_PERFORMANCE** - Assess profitability and adjust strategy
11. **ERROR_RECOVERY** - Handle failures and retry operations

### State Transitions

```
INITIALIZE → ASSESS_SITUATION
ASSESS_SITUATION → NEGOTIATE_CONTRACT (if no active contracts)
ASSESS_SITUATION → EXECUTE_CONTRACT (if active contract exists)
NEGOTIATE_CONTRACT → ACCEPT_CONTRACT (if suitable contracts found)
NEGOTIATE_CONTRACT → ERROR_RECOVERY (if no contracts available)
ACCEPT_CONTRACT → PLAN_FULFILLMENT (if contract accepted)
ACCEPT_CONTRACT → NEGOTIATE_CONTRACT (if contract rejected)
PLAN_FULFILLMENT → ACQUIRE_RESOURCES (if resources needed)
PLAN_FULFILLMENT → EXECUTE_CONTRACT (if ready to proceed)
ACQUIRE_RESOURCES → EXECUTE_CONTRACT (if acquisition successful)
ACQUIRE_RESOURCES → ERROR_RECOVERY (if cannot acquire resources)
EXECUTE_CONTRACT → DELIVER_GOODS (if contract terms met)
EXECUTE_CONTRACT → ERROR_RECOVERY (if execution fails)
DELIVER_GOODS → COMPLETE_CONTRACT (if delivery successful)
DELIVER_GOODS → ERROR_RECOVERY (if delivery fails)
COMPLETE_CONTRACT → EVALUATE_PERFORMANCE
EVALUATE_PERFORMANCE → ASSESS_SITUATION (continuous loop)
ERROR_RECOVERY → ASSESS_SITUATION (after error handling)
```

## Detailed State Logic

### 1. INITIALIZE
**Purpose**: Set up agent and establish API connection

**API Calls**:
- `POST /register` - Register new agent (if first run)
- `GET /my/agent` - Verify agent status and retrieve basic information

**Logic**:
- Register agent if not exists
- Verify API authentication
- Initialize logging and monitoring systems
- Transition to ASSESS_SITUATION

### 2. ASSESS_SITUATION
**Purpose**: Evaluate current agent state and determine next action

**API Calls**:
- `GET /my/agent` - Get current credits, headquarters location
- `GET /my/ships` - List all owned ships and their status
- `GET /my/contracts` - List active and available contracts
- `GET /systems/{systemSymbol}/waypoints` - Check local waypoints and markets

**Logic**:
- Check if agent has active contracts
- Evaluate ship readiness and cargo capacity
- Assess available credits for operations
- Determine if ready to execute existing contract or need new one
- Transition based on current situation

### 3. NEGOTIATE_CONTRACT
**Purpose**: Find and evaluate available contracts

**API Calls**:
- `GET /my/contracts` - Get list of available contracts
- `GET /systems/{systemSymbol}/waypoints/{waypointSymbol}` - Check contract locations
- `GET /systems/{systemSymbol}/waypoints/{waypointSymbol}/market` - Verify market availability for required goods

**Logic**:
- Filter contracts by agent capabilities (ship capacity, location accessibility)
- Calculate profitability: (contract payment - estimated costs)
- Prioritize contracts by profit margin and completion time
- Select best contract candidate
- Transition to ACCEPT_CONTRACT

### 4. ACCEPT_CONTRACT
**Purpose**: Formally accept the selected contract

**API Calls**:
- `POST /my/contracts/{contractId}/accept` - Accept the contract

**Logic**:
- Accept the highest priority contract
- Store contract details for execution planning
- Handle acceptance failures (contract taken, insufficient funds)
- Transition to PLAN_FULFILLMENT on success

### 5. PLAN_FULFILLMENT
**Purpose**: Analyze contract requirements and create execution plan

**API Calls**:
- `GET /my/contracts/{contractId}` - Get detailed contract requirements
- `GET /systems/{systemSymbol}` - Get system information for navigation planning
- `GET /systems/{systemSymbol}/waypoints/{waypointSymbol}/market` - Check markets for required goods

**Logic**:
- Parse contract delivery requirements (goods, quantities, destinations)
- Calculate total cargo space needed
- Identify source markets for required goods
- Plan navigation route (pickup → delivery locations)
- Estimate fuel and time requirements
- Determine if additional ships needed
- Transition based on resource needs

### 6. ACQUIRE_RESOURCES
**Purpose**: Purchase additional ships or upgrade existing ones if needed

**API Calls**:
- `GET /systems/{systemSymbol}/waypoints/{waypointSymbol}/shipyard` - Check available ships
- `POST /my/ships` - Purchase new ship
- `POST /my/ships/{shipSymbol}/mounts` - Install cargo modules
- `POST /my/ships/{shipSymbol}/refuel` - Refuel ships

**Logic**:
- Calculate required cargo capacity vs. available capacity
- Purchase additional ships if credits allow
- Install cargo modules to maximize capacity
- Ensure all ships are fueled for planned routes
- Transition to EXECUTE_CONTRACT when ready

### 7. EXECUTE_CONTRACT
**Purpose**: Navigate ships and acquire required goods

**API Calls**:
- `POST /my/ships/{shipSymbol}/navigate` - Move ship to waypoint
- `POST /my/ships/{shipSymbol}/dock` - Dock at waypoints
- `POST /my/ships/{shipSymbol}/orbit` - Leave waypoints
- `GET /systems/{systemSymbol}/waypoints/{waypointSymbol}/market` - Check market prices
- `POST /my/ships/{shipSymbol}/purchase` - Buy required goods
- `POST /my/ships/{shipSymbol}/refuel` - Refuel as needed

**Logic**:
- Navigate ships to source markets
- Purchase required goods at best available prices
- Manage cargo space efficiently
- Handle market fluctuations and availability
- Navigate to delivery destinations
- Track progress against contract requirements
- Transition to DELIVER_GOODS when goods acquired

### 8. DELIVER_GOODS
**Purpose**: Complete contract deliveries

**API Calls**:
- `POST /my/ships/{shipSymbol}/navigate` - Move to delivery waypoint
- `POST /my/ships/{shipSymbol}/dock` - Dock for delivery
- `POST /my/contracts/{contractId}/deliver` - Deliver goods for contract
- `GET /my/contracts/{contractId}` - Verify delivery progress

**Logic**:
- Navigate to contract delivery waypoint
- Dock and deliver required goods
- Verify delivery quantities match contract requirements
- Handle partial deliveries if multiple trips needed
- Transition to COMPLETE_CONTRACT when all goods delivered

### 9. COMPLETE_CONTRACT
**Purpose**: Finalize contract and collect payment

**API Calls**:
- `POST /my/contracts/{contractId}/fulfill` - Fulfill completed contract
- `GET /my/agent` - Check updated credits and reputation

**Logic**:
- Fulfill the contract to receive payment
- Record contract completion metrics
- Update agent status with new credits
- Transition to EVALUATE_PERFORMANCE

### 10. EVALUATE_PERFORMANCE
**Purpose**: Analyze contract profitability and adjust strategy

**API Calls**:
- `GET /my/agent` - Get current agent stats
- `GET /my/ships` - Review ship conditions

**Logic**:
- Calculate actual profit: (contract payment - total costs)
- Track completion time and efficiency metrics
- Update strategy parameters based on performance
- Identify optimization opportunities
- Transition to ASSESS_SITUATION for next cycle

### 11. ERROR_RECOVERY
**Purpose**: Handle failures and exceptions

**API Calls**:
- Various API calls to diagnose issues
- Retry failed operations with exponential backoff

**Logic**:
- Log error details for analysis
- Determine if error is recoverable
- Retry transient failures with delays
- Abandon problematic contracts if necessary
- Reset agent state to stable condition
- Transition to ASSESS_SITUATION to continue operations

## Key Decision Points

1. **Contract Selection Criteria**:
   - Profit margin > minimum threshold (e.g., 10% of current credits)
   - Required goods available in accessible markets
   - Total cargo requirements within fleet capacity
   - Delivery locations within reasonable distance

2. **Resource Acquisition Triggers**:
   - Cargo capacity < contract requirements
   - Ship count insufficient for parallel operations
   - Credits available > ship cost + safety margin

3. **Error Handling Strategies**:
   - Market unavailability: Find alternative sources
   - Navigation failures: Recalculate routes
   - Insufficient funds: Accept smaller contracts
   - Contract conflicts: Prioritize by profitability

## Success Metrics

- Credits earned per hour
- Contract completion rate
- Average profit margin
- Fleet utilization efficiency
- Error recovery time

This state machine ensures continuous operation while adapting to changing market conditions and optimizing for profitability.