Feature: Amazon Cart Item Addition & Badge Counter
  As an Amazon customer
  I want my shopping cart counter to update immediately
  So that I can see the total items in my cart

  @cart @amazon @regression
  Scenario: Add item to cart from product details page
    Given user is on Amazon product detail page
    When user clicks add to cart button
    Then cart count badge should show 1
