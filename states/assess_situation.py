"""
ASSESS_SITUATION state implementation.

This state evaluates the current agent situation and determines the next action.
"""

from typing import Optional
from models.state_enums import AgentState
from states.base_state import BaseState
from models.agent_data import AgentData
from models.contract import Contract
from models.ship import Ship


class AssessSituationState(BaseState):
    """
    State for assessing the current agent situation.
    
    This state:
    1. Updates agent data (credits, ships, contracts)
    2. Evaluates current contracts and ship readiness
    3. Determines the next appropriate action
    """
    
    def execute(self) -> Optional[AgentState]:
        """
        Execute the ASSESS_SITUATION state logic.
        
        Returns:
            AgentState: Next state to transition to
        """
        self.log_state_entry()
        
        try:
            # Step 1: Update agent data
            self._update_agent_data()
            
            # Step 2: Update ship information
            self._update_ships()
            
            # Step 3: Update contract information
            self._update_contracts()
            
            # Step 4: Assess situation and determine next action
            next_state = self._determine_next_action()
            
            self.log_state_exit(next_state)
            return next_state
            
        except Exception as e:
            self.logger.error(f"Error in ASSESS_SITUATION state: {e}")
            return AgentState.ERROR_RECOVERY
    
    def _update_agent_data(self) -> None:
        """Update agent data from API."""
        self.logger.info("Updating agent data...")
        
        try:
            response = self.api_client.get_my_agent()
            self.context.update_agent_data(response)
            
            if self.context.agent_data:
                self.logger.info(f"Agent: {self.context.agent_data.symbol}")
                self.logger.info(f"Credits: {self.context.agent_data.credits:,}")
                self.logger.info(f"Headquarters: {self.context.agent_data.headquarters}")
                self.logger.info(f"Ships: {self.context.agent_data.ship_count}")
        
        except Exception as e:
            self.logger.error(f"Failed to update agent data: {e}")
            raise
    
    def _update_ships(self) -> None:
        """Update ship information from API."""
        self.logger.info("Updating ship information...")
        
        try:
            response = self.api_client.get_my_ships()
            ships_data = response.get('data', [])
            
            # Convert API response to Ship objects
            self.context.ships = [
                Ship.from_api_response(ship_data)
                for ship_data in ships_data
            ]
            
            self.logger.info(f"Found {len(self.context.ships)} ships")
            
            # Log ship details
            for ship in self.context.ships:
                self.logger.info(
                    f"Ship {ship.symbol}: {ship.role.value} at {ship.nav.waypoint_symbol} "
                    f"({ship.nav.status.value}) - Cargo: {ship.cargo.units}/{ship.cargo.capacity}"
                )
                
                if ship.fuel.needs_refuel:
                    self.logger.warning(f"Ship {ship.symbol} needs refueling ({ship.fuel.percentage:.1f}%)")
        
        except Exception as e:
            self.logger.error(f"Failed to update ship information: {e}")
            raise
    
    def _update_contracts(self) -> None:
        """Update contract information from API."""
        self.logger.info("Updating contract information...")
        
        try:
            response = self.api_client.get_my_contracts()
            contracts_data = response.get('data', [])
            
            # Convert API response to Contract objects
            contracts = [
                Contract.from_api_response(contract_data)
                for contract_data in contracts_data
            ]
            
            # Find active contract (accepted but not fulfilled)
            active_contracts = [
                contract for contract in contracts
                if contract.accepted and not contract.fulfilled and not contract.is_expired
            ]
            
            if active_contracts:
                # Use the first active contract
                self.context.current_contract = active_contracts[0]
                self.logger.info(f"Active contract: {self.context.current_contract.contract_id}")
                self._log_contract_details(self.context.current_contract)
            else:
                self.context.current_contract = None
                self.logger.info("No active contracts found")
            
            # Log available contracts
            available_contracts = [
                contract for contract in contracts
                if not contract.accepted and not contract.is_expired
            ]
            
            if available_contracts:
                self.logger.info(f"Found {len(available_contracts)} available contracts")
            else:
                self.logger.info("No available contracts found")
        
        except Exception as e:
            self.logger.error(f"Failed to update contract information: {e}")
            raise
    
    def _log_contract_details(self, contract: Contract) -> None:
        """Log details of a contract."""
        self.logger.info(f"Contract {contract.contract_id} details:")
        self.logger.info(f"  Type: {contract.contract_type.value}")
        self.logger.info(f"  Faction: {contract.faction_symbol}")
        self.logger.info(f"  Payment: {contract.terms.total_payment:,} credits")
        self.logger.info(f"  Deadline: {contract.terms.deadline}")
        
        for i, delivery in enumerate(contract.terms.deliveries):
            remaining = delivery.remaining_units
            total = delivery.units_required
            self.logger.info(
                f"  Delivery {i+1}: {remaining}/{total} {delivery.trade_symbol} "
                f"to {delivery.destination_symbol}"
            )
    
    def _determine_next_action(self) -> AgentState:
        """
        Determine the next action based on current situation.
        
        Returns:
            AgentState: Next state to transition to
        """
        self.logger.info("Determining next action...")
        
        # Check if we have ships
        if not self.context.ships:
            self.logger.warning("No ships available - this shouldn't happen!")
            return AgentState.ERROR_RECOVERY
        
        # Check if we have an active contract
        if self.context.current_contract:
            self.logger.info("Active contract found - continuing execution")
            
            # Check if contract is completed
            if self.context.current_contract.all_deliveries_completed:
                self.logger.info("All deliveries completed - ready to fulfill contract")
                return AgentState.COMPLETE_CONTRACT
            else:
                self.logger.info("Contract deliveries incomplete - continuing execution")
                return AgentState.EXECUTE_CONTRACT
        
        # No active contract - need to negotiate a new one
        self.logger.info("No active contract - negotiating new contract")
        return AgentState.NEGOTIATE_CONTRACT
    
    def _assess_ship_readiness(self) -> dict:
        """
        Assess the readiness of ships for contract execution.
        
        Returns:
            dict: Assessment results with readiness status and issues
        """
        assessment = {
            'ready_ships': [],
            'ships_needing_fuel': [],
            'ships_in_transit': [],
            'total_cargo_capacity': 0,
            'available_cargo_space': 0
        }
        
        for ship in self.context.ships:
            assessment['total_cargo_capacity'] += ship.cargo_capacity
            assessment['available_cargo_space'] += ship.get_available_cargo_space()
            
            if ship.nav.is_in_transit:
                assessment['ships_in_transit'].append(ship.symbol)
            elif ship.fuel.needs_refuel:
                assessment['ships_needing_fuel'].append(ship.symbol)
            else:
                assessment['ready_ships'].append(ship.symbol)
        
        return assessment