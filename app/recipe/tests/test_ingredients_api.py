from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Ingredient, Recipe

from recipe.serializers import IngredientSerializer


INGREDIENTS_URL = reverse('recipe:ingredient-list')


class PublicIngredientsAPITests(TestCase):
    """Test the publicly available ingredients API"""

    def setUp(self):
        self.client = APIClient()

    def test_login_required(self):
        """Test that login required for getting ingredients"""
        res = self.client.get(INGREDIENTS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredientsAPITests(TestCase):
    """Test the private ingrdeients API"""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            'test@example.com',
            'password123'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_ingredients(self):
        """Test getting ingredients"""
        Ingredient.objects.create(user=self.user, name="Kale")
        Ingredient.objects.create(user=self.user, name="Salt")

        res = self.client.get(INGREDIENTS_URL)

        ingredients = Ingredient.objects.all().order_by('-name')
        serializer = IngredientSerializer(ingredients, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_tags_limited_to_user(self):
        """Test user only sees their own tags"""
        user2 = get_user_model().objects.create_user(
            'someoneelse@example.com',
            'password'
        )
        Ingredient.objects.create(user=user2, name='Sausage')
        ingredient = Ingredient.objects.create(user=self.user, name='Vinegar')

        res = self.client.get(INGREDIENTS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], ingredient.name)

    def test_create_ingredient_successful(self):
        """Test creating a new ingredient"""
        payload = {'name': 'ingredient'}
        self.client.post(INGREDIENTS_URL, payload)

        exists = Ingredient.objects.filter(
            user=self.user,
            name=payload['name']
        ).exists()

        self.assertTrue(exists)

    def test_create_ingredient_invalid(self):
        """Test creating a new ingredient with invalid payload"""
        payload = {'name': ''}
        res = self.client.post(INGREDIENTS_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_ingredientss_assigned_to_recipes(self):
        """Test only ingredientss with recipes returned"""
        ingredients1 = Ingredient.objects.create(user=self.user, name="Lunch")
        ingredients2 = Ingredient.objects.create(user=self.user, name="Dinner")
        recipe = Recipe.objects.create(
            title='Ming on toast',
            time_minutes=10,
            price=20.00,
            user=self.user,
        )

        recipe.ingredients.add(ingredients1)

        res = self.client.get(INGREDIENTS_URL, {'assigned_only': 1})

        serializer1 = IngredientSerializer(ingredients1)
        serializer2 = IngredientSerializer(ingredients2)

        self.assertIn(serializer1.data, res.data)
        self.assertNotIn(serializer2.data, res.data)

    def test_retrieve_assigned_unique(self):
        """Test only unique ingredients returned"""

        ingredient = Ingredient.objects.create(user=self.user, name="flour")
        Ingredient.objects.create(user=self.user, name="apples")

        recipe1 = Recipe.objects.create(
            title='Pancakes',
            time_minutes=15,
            price=20.00,
            user=self.user,
        )
        recipe1.ingredients.add(ingredient)
        recipe2 = Recipe.objects.create(
            title='Cake',
            time_minutes=15,
            price=20.00,
            user=self.user,
        )
        recipe2.ingredients.add(ingredient)

        res = self.client.get(INGREDIENTS_URL, {'assigned_only': 1})

        self.assertEqual(len(res.data), 1)
