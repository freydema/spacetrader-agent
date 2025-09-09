"""
NEGOTIATE_CONTRACT state implementation.

This state finds and evaluates available contracts, selecting the best one for acceptance.
"""

from typing import Optional, List
from models.state_enums import AgentState
from states.base_state import BaseState
from models.contract import Contract


class NegotiateContractState(BaseState):
    """
    State for finding and evaluating available contracts.
    
    This state:
    1. Retrieves available contracts from the API
    2. Filters contracts based on agent capabilities
    3. Calculates profitability scores for each contract
    4. Selects the best contract for acceptance
    """
    
    def execute(self) -> Optional[AgentState]:
        """
        Execute the NEGOTIATE_CONTRACT state logic.
        
        Returns:
            AgentState: Next state to transition to (ACCEPT_CONTRACT or ERROR_RECOVERY)
        """
        self.log_state_entry()
        
        try:
            # Step 1: Get available contracts
            available_contracts = self._get_available_contracts()
            
            if not available_contracts:
                self.logger.warning("No available contracts found")
                # Wait a bit before trying again
                import time
                time.sleep(10)
                return AgentState.NEGOTIATE_CONTRACT
            
            # Step 2: Filter contracts by capabilities
            suitable_contracts = self._filter_contracts_by_capabilities(available_contracts)
            
            if not suitable_contracts:
                self.logger.warning("No suitable contracts found for current capabilities")
                
                # Analyze why contracts were filtered out
                next_action = self._analyze_filtering_reasons(available_contracts)
                
                if next_action == AgentState.ACQUIRE_RESOURCES:
                    self.logger.info("Need to acquire more resources (ships/capacity) to handle available contracts")
                    next_state = AgentState.ACQUIRE_RESOURCES
                    self.log_state_exit(next_state)
                    return next_state
                else:
                    # Wait before trying again if it's a temporary issue
                    import time
                    time.sleep(30)  # Longer wait for contracts to potentially change
                    return AgentState.NEGOTIATE_CONTRACT
            
            # Step 3: Evaluate and rank contracts
            best_contract = self._select_best_contract(suitable_contracts)
            
            if best_contract:
                self.context.current_contract = best_contract
                self.logger.info(f"Selected contract {best_contract.contract_id} for acceptance")
                self._log_contract_details(best_contract)
                
                next_state = AgentState.ACCEPT_CONTRACT
                self.log_state_exit(next_state)
                return next_state
            else:
                self.logger.warning("No profitable contracts found")
                # Wait before trying again
                import time
                time.sleep(10)
                return AgentState.NEGOTIATE_CONTRACT
                
        except Exception as e:
            self.logger.error(f"Error in NEGOTIATE_CONTRACT state: {e}")
            return AgentState.ERROR_RECOVERY
    
    def _get_available_contracts(self) -> List[Contract]:
        """
        Retrieve available contracts from the API.
        
        Returns:
            List[Contract]: List of available contracts
        """
        self.logger.info("Retrieving available contracts...")
        
        try:
            # Get contracts from API
            response = self.api_client.get_my_contracts()
            contracts_data = response.get('data', [])
            
            # Convert to Contract objects
            all_contracts = [
                Contract.from_api_response(contract_data)
                for contract_data in contracts_data
            ]
            
            # Filter for available (not accepted, not expired) contracts
            available_contracts = [
                contract for contract in all_contracts
                if not contract.accepted and not contract.fulfilled and not contract.is_expired
            ]
            
            self.logger.info(f"Found {len(available_contracts)} available contracts out of {len(all_contracts)} total")
            
            return available_contracts
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve contracts: {e}")
            raise
    
    def _filter_contracts_by_capabilities(self, contracts: List[Contract]) -> List[Contract]:
        """
        Filter contracts based on agent capabilities.
        
        Args:
            contracts: List of contracts to filter
            
        Returns:
            List[Contract]: Contracts that the agent can potentially fulfill
        """
        self.logger.info("Filtering contracts by agent capabilities...")
        
        if not self.context.ships:
            self.logger.warning("No ships available for contract evaluation")
            return []
        
        suitable_contracts = []
        total_cargo_capacity = self.context.get_total_cargo_capacity()
        
        for contract in contracts:
            # Check if we have enough total cargo capacity
            total_units_needed = sum(delivery.units_required for delivery in contract.terms.deliveries)
            
            if total_units_needed > total_cargo_capacity:
                self.logger.info(f"Contract {contract.contract_id} requires {total_units_needed} units, "
                                f"but we only have {total_cargo_capacity} capacity - skipping")
                continue
            
            # Check if we have sufficient credits for potential costs
            estimated_cost = self._estimate_contract_cost(contract)
            if not self.context.has_sufficient_credits(estimated_cost):
                self.logger.info(f"Contract {contract.contract_id} estimated cost {estimated_cost:,} "
                                f"exceeds available credits - skipping")
                continue
            
            # Check if we can handle deliveries with our fleet (allowing multi-ship deliveries)
            # For now, we'll be more permissive - if total capacity > total required, we can handle it
            # A more sophisticated implementation could check if deliveries can be split optimally
            max_delivery_size = max(
                (delivery.units_required for delivery in contract.terms.deliveries),
                default=0
            )
            largest_ship_capacity = max((ship.cargo_capacity for ship in self.context.ships), default=0)
            
            # Only filter out if even our largest ship can't handle the biggest delivery
            # AND we don't have enough total capacity (safety check)
            if max_delivery_size > largest_ship_capacity and total_units_needed > total_cargo_capacity:
                self.logger.info(f"Contract {contract.contract_id} largest delivery ({max_delivery_size} units) "
                                f"exceeds largest ship capacity ({largest_ship_capacity}) and total requirement "
                                f"({total_units_needed}) exceeds total capacity ({total_cargo_capacity}) - skipping")
                continue
            elif max_delivery_size > largest_ship_capacity:
                self.logger.info(f"Contract {contract.contract_id} largest delivery ({max_delivery_size} units) "
                                f"exceeds largest ship ({largest_ship_capacity}), but may be splittable across fleet - keeping")
            
            # Log acceptance reason for debugging
            self.logger.info(f"Contract {contract.contract_id} passed ship capacity check - "
                            f"largest delivery: {max_delivery_size}, largest ship: {largest_ship_capacity}, "
                            f"total required: {total_units_needed}, total capacity: {total_cargo_capacity}")
            
            suitable_contracts.append(contract)
        
        self.logger.info(f"Found {len(suitable_contracts)} suitable contracts after filtering")
        return suitable_contracts
    
    def _analyze_filtering_reasons(self, contracts: List[Contract]) -> AgentState:
        """
        Analyze why contracts were filtered out and determine the best action.
        
        Args:
            contracts: List of contracts that were evaluated
            
        Returns:
            AgentState: Recommended next action
        """
        if not contracts:
            return AgentState.NEGOTIATE_CONTRACT
        
        total_cargo_capacity = self.context.get_total_cargo_capacity()
        capacity_issues = 0
        credit_issues = 0
        ship_size_issues = 0
        
        for contract in contracts:
            total_units_needed = sum(delivery.units_required for delivery in contract.terms.deliveries)
            estimated_cost = self._estimate_contract_cost(contract)
            max_delivery_size = max(
                (delivery.units_required for delivery in contract.terms.deliveries),
                default=0
            )
            
            # Count reasons for filtering
            if total_units_needed > total_cargo_capacity:
                capacity_issues += 1
            
            if not self.context.has_sufficient_credits(estimated_cost):
                credit_issues += 1
            
            largest_ship_capacity = max((ship.cargo_capacity for ship in self.context.ships), default=0)
            # Only count as ship size issue if largest delivery exceeds largest ship AND total exceeds total capacity
            if max_delivery_size > largest_ship_capacity and total_units_needed > total_cargo_capacity:
                ship_size_issues += 1
        
        self.logger.info(f"Contract filtering analysis: "
                        f"capacity issues: {capacity_issues}/{len(contracts)}, "
                        f"credit issues: {credit_issues}/{len(contracts)}, "
                        f"ship size issues: {ship_size_issues}/{len(contracts)}")
        
        # Prioritize solutions based on most common issues
        if capacity_issues > 0 or ship_size_issues > 0:
            # Need more or bigger ships
            if self.context.agent_data and self.context.agent_data.credits > 50000:  # Rough ship cost
                
                # Check if we recently failed to acquire resources
                last_attempt = self.context.strategy_config.get('last_acquire_attempt', 0)
                acquire_failed = self.context.strategy_config.get('acquire_failed', False)
                import time
                
                # Only try to acquire resources if we haven't recently failed
                if not acquire_failed or (time.time() - last_attempt) > 3600:  # 1 hour cooldown
                    return AgentState.ACQUIRE_RESOURCES
                else:
                    self.logger.info("Recently failed to acquire resources, will wait for suitable contracts")
        
        # If it's mainly credit issues, or we don't have enough credits for ships
        # Just wait for different contracts or more credits from other sources
        return AgentState.NEGOTIATE_CONTRACT
    
    def _estimate_contract_cost(self, contract: Contract) -> int:
        """
        Estimate the cost to fulfill a contract.
        
        Args:
            contract: Contract to estimate costs for
            
        Returns:
            int: Estimated cost in credits
        """
        # Simple cost estimation - in a real implementation, this would be more sophisticated
        # For now, estimate based on goods volume and potential fuel costs
        
        total_units = sum(delivery.units_required for delivery in contract.terms.deliveries)
        
        # Rough estimates:
        # - 100 credits per unit for goods (very rough average)
        # - 10% of payment for fuel and other costs
        estimated_goods_cost = total_units * 100
        estimated_fuel_cost = int(contract.terms.total_payment * 0.1)
        
        total_cost = estimated_goods_cost + estimated_fuel_cost
        
        self.logger.info(f"Contract {contract.contract_id} estimated cost: {total_cost:,} "
                         f"(goods: {estimated_goods_cost:,}, fuel: {estimated_fuel_cost:,})")
        
        return total_cost
    
    def _select_best_contract(self, contracts: List[Contract]) -> Optional[Contract]:
        """
        Select the best contract from suitable options.
        
        Args:
            contracts: List of suitable contracts
            
        Returns:
            Optional[Contract]: Best contract, or None if none are profitable
        """
        self.logger.info(f"Evaluating {len(contracts)} contracts for profitability...")
        
        if not contracts:
            return None
        
        cargo_capacity = self.context.get_total_cargo_capacity()
        contract_scores = []
        
        for contract in contracts:
            estimated_cost = self._estimate_contract_cost(contract)
            score = contract.calculate_profitability_score(cargo_capacity, estimated_cost)
            
            contract_scores.append((contract, score, estimated_cost))
            
            profit = contract.terms.total_payment - estimated_cost
            profit_margin = (profit / contract.terms.total_payment) * 100 if contract.terms.total_payment > 0 else 0
            
            self.logger.info(f"Contract {contract.contract_id}: "
                           f"Payment: {contract.terms.total_payment:,}, "
                           f"Est. Cost: {estimated_cost:,}, "
                           f"Profit: {profit:,} ({profit_margin:.1f}%), "
                           f"Score: {score:.2f}")
        
        # Sort by score (highest first)
        contract_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Select the best contract if it has a positive score
        if contract_scores and contract_scores[0][1] > 0:
            best_contract, best_score, best_cost = contract_scores[0]
            
            profit = best_contract.terms.total_payment - best_cost
            self.logger.info(f"Selected best contract {best_contract.contract_id} "
                           f"with score {best_score:.2f} and expected profit {profit:,}")
            
            return best_contract
        else:
            self.logger.warning("No contracts with positive profitability scores found")
            return None
    
    def _log_contract_details(self, contract: Contract) -> None:
        """Log details of the selected contract."""
        self.logger.info(f"Contract {contract.contract_id} details:")
        self.logger.info(f"  Type: {contract.contract_type.value}")
        self.logger.info(f"  Faction: {contract.faction_symbol}")
        self.logger.info(f"  Payment: {contract.terms.total_payment:,} credits")
        self.logger.info(f"    - On Accept: {contract.terms.payment_on_accepted:,}")
        self.logger.info(f"    - On Fulfill: {contract.terms.payment_on_fulfilled:,}")
        self.logger.info(f"  Deadline: {contract.terms.deadline}")
        
        for i, delivery in enumerate(contract.terms.deliveries, 1):
            self.logger.info(f"  Delivery {i}: {delivery.units_required} {delivery.trade_symbol} "
                           f"to {delivery.destination_symbol}")
        
        # Calculate time remaining
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        time_remaining = contract.terms.deadline - now
        hours_remaining = time_remaining.total_seconds() / 3600
        self.logger.info(f"  Time remaining: {hours_remaining:.1f} hours")