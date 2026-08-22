Feature: Checkout Process on Amazon
  As a shopper on Amazon
  I want to complete the checkout process
  So that I can purchase the items in my cart

  Background:
    Given I am logged into my Amazon account
    And I have at least 1 item in my cart
    And I proceed to checkout

  Scenario: Complete checkout using an existing saved address and payment method
    Given I have a saved shipping address and a saved payment method on file
    When I select the saved shipping address
    And I select the saved payment method
    And I click "Place your order"
    Then I should see an order confirmation page
    And I should receive an order confirmation email

  Scenario: Add a new shipping address during checkout
    When I click "Add a new address"
    And I fill in a valid shipping address
    And I save the address
    Then the new address should appear as a selectable shipping option
    And it should be selected as the default for this order

  Scenario: Checkout fails with an expired payment card
    Given my saved payment method is an expired credit card
    When I select the expired card as my payment method
    And I click "Place your order"
    Then I should see an error message indicating the card has expired
    And I should be prompted to update or choose a different payment method

  Scenario: Apply a valid promotional code at checkout
    When I enter a valid promotional code in the "Gift cards & promotional codes" field
    And I click "Apply"
    Then the order total should be reduced by the promotional discount
    And I should see the discount itemized in the order summary

  Scenario: Order total correctly includes tax and shipping
    Given my cart subtotal is a known, fixed amount
    When I reach the final review step of checkout
    Then the order summary should display subtotal, estimated tax, and shipping separately
    And the order total should equal the sum of those three values
