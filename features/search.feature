Feature: Product Search Auto-Complete
  As a store customer
  I want search suggestions while typing in the search bar
  So that I can quickly locate relevant items

  @search @autocomplete
  Scenario: Search for single word query
    Given the user is on the store homepage
    When the user types "laptop" into the search bar
    Then auto-complete suggestions should display matching products
