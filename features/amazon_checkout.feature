Feature: Amazon Order Checkout & Promo Code Discount
  As a customer
  I want to apply discount promo codes at checkout
  So that I get appropriate discounts on my purchases

  @checkout @promo @smoke
  Scenario: Apply single valid promo code during standard checkout
    Given I have items worth 00 in my cart
    When I proceed to standard checkout
    And I apply promo code "SUMMER15"
    Then I should see a 15% discount applied to my subtotal
    And the total order price should update to 5.00
