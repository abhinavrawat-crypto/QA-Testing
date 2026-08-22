Feature: Add to Cart on Amazon
  As a shopper on Amazon
  I want to add products to my shopping cart
  So that I can purchase multiple items together

  Background:
    Given I am logged into my Amazon account
    And I am viewing a product detail page for an in-stock item

  Scenario: Add a single item to an empty cart
    When I click the "Add to Cart" button
    Then the cart icon should update to show "1" item
    And I should see a confirmation message that the item was added

  Scenario: Increase quantity of an item already in the cart
    Given I have already added 1 unit of this item to my cart
    When I change the quantity selector to 3
    And I click "Update"
    Then my cart should show 3 units of this item
    And the subtotal should reflect the price for 3 units

  Scenario: Add to cart is blocked for an out-of-stock item
    Given the product is currently out of stock
    Then the "Add to Cart" button should be disabled or hidden
    And I should see a "Currently unavailable" message instead

  Scenario: Remove an item from the cart
    Given I have at least 1 item in my cart
    When I open my cart
    And I click "Delete" on that item
    Then the item should no longer appear in my cart
    And the cart item count should decrease by 1

  Scenario: Cart persists items after logging out and back in
    Given I have added 2 items to my cart
    When I log out of my Amazon account
    And I log back in with the same account
    Then my cart should still contain the same 2 items
