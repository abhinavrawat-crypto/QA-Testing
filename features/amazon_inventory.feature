Feature: Flash Sale Item Inventory Reservation & Expiry Lock
  As a store manager
  I want flash sale cart items reserved during checkout
  So that inventory is locked fairly during high-concurrency promotions

  @inventory @flash-sale @concurrency
  Scenario: Reserve inventory during flash sale checkout
    Given a flash sale item has 10 units in stock
    When a buyer adds 1 unit to cart and initiates checkout
    Then the stock reservation timer should start for 120 seconds
    And stock should show 9 units available to other buyers
