Feature: Cart Order Total & Shipping Calculation
  As a customer
  I want shipping fees calculated accurately in my order total
  So that I know the final total before placing an order

  @cart @shipping @regression
  Scenario: Calculate flat shipping fee on checkout
    Given the user has items worth 0 in cart
    When the user selects standard shipping
    Then .00 shipping fee should be added to subtotal
    And total order price should display 5.00
