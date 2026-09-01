Feature: Amazon Product Search & Auto-Suggest
  As an Amazon shopper
  I want search suggestions while typing in the search box
  So that I can quickly find products on Amazon India and Amazon US

  @search @amazon
  Scenario: Search product on Amazon home page
    Given user is on Amazon home page
    When user types "laptop" into the search box
    Then search suggestions should appear
