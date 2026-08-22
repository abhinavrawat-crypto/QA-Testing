Feature: Wishlist on Amazon
  As a shopper on Amazon
  I want to save products to a wishlist
  So that I can keep track of items I'm interested in for later

  Background:
    Given I am logged into my Amazon account
    And I am viewing a product detail page

  Scenario: Add a product to the default wishlist
    When I click "Add to List"
    And I select my default wishlist
    Then the product should appear in my default wishlist
    And I should see a confirmation that the item was added

  Scenario: Create a new named wishlist and add a product to it
    When I click "Add to List"
    And I select "Create a new list"
    And I name the list "Birthday Gift Ideas"
    And I save the new list
    Then the product should appear under the "Birthday Gift Ideas" list
    And "Birthday Gift Ideas" should appear in my list of wishlists going forward

  Scenario: Remove a product from a wishlist
    Given a product is already saved in one of my wishlists
    When I open that wishlist
    And I remove the product from the list
    Then the product should no longer appear in that wishlist

  Scenario: Move an item from wishlist directly to cart
    Given a product is saved in one of my wishlists
    When I open that wishlist
    And I click "Add to Cart" next to the item
    Then the item should be added to my shopping cart
    And I should still see the item remaining in the wishlist unless I explicitly remove it

  Scenario: Wishlist is accessible and unchanged across sessions
    Given I have saved 3 items to a wishlist
    When I log out and log back in on a different day
    And I navigate to my wishlists
    Then I should still see all 3 previously saved items in that wishlist
