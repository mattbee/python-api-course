import tempfile
import os
from PIL import Image

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Recipe, Tag, Ingredient

from recipe.serializers import RecipeSerializer, RecipeDetailSerializer


RECIPES_URL = reverse('recipe:recipe-list')


def detail_url(recipe_id):
    """Return recipe url"""
    return reverse('recipe:recipe-detail', args=[recipe_id])


def sample_tag(user, name="Main course"):
    """Create and return simple tag"""
    return Tag.objects.create(user=user, name=name)


def sample_ingredient(user, name="Pork"):
    """Create and return sample ingredient"""
    return Ingredient.objects.create(user=user, name=name)


def sample_recipe(user, **params):
    """Create a sample recipe"""
    defaults = {
        'title': 'Sample recipe',
        'time_minutes': 10,
        'price': 5.00
    }

    defaults.update(params)

    return Recipe.objects.create(user=user, **defaults)


def image_upload_url(recipe_id):
    """Return url for recipe image upload"""
    return reverse('recipe:recipe-upload-image', args=[recipe_id])


class PublicRecipeAPITests(TestCase):
    """Test unauthed """

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test auth required"""
        res = self.client.get(RECIPES_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeAPITests(TestCase):
    """Test authenticated recipe access"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'test@example.com',
            'password'
        )
        self.client.force_authenticate(self.user)

    def test_retrieve_recipes(self):
        """Test retrieveing receipes"""
        sample_recipe(user=self.user)
        sample_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)

        recipes = Recipe.objects.all().order_by('-id')
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_receipes_limited_to_user(self):
        """Test get only own recipes"""
        user2 = get_user_model().objects.create_user(
            'someoneelse@example.com',
            'password'
        )

        sample_recipe(user=user2)
        sample_recipe(user=self.user)

        res = self.client.get(RECIPES_URL)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data, serializer.data)

    def test_view_recipe_detail(self):
        """View recipe"""
        recipe = sample_recipe(user=self.user)
        recipe.tags.add(sample_tag(user=self.user))
        recipe.ingredients.add(sample_ingredient(user=self.user))

        url = detail_url(recipe.id)
        res = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)

        self.assertEqual(res.data, serializer.data)

    def test_create_basic_recipe(self):
        """Test creating recipes"""
        payload = {
            'title': 'Chocolate cheesecake',
            'time_minutes': 30,
            'price': 4.00
        }

        res = self.client.post(RECIPES_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data['id'])
        for key in payload.keys():
            self.assertEqual(payload[key], getattr(recipe, key))

    def test_create_recipe_with_tags(self):
        """Test create recipe with tags"""
        tag1 = sample_tag(user=self.user, name='Vegan')
        tag2 = sample_tag(user=self.user, name='Dessert')

        payload = {
            'title': 'Avocado Lime Cheesecake',
            'tags': [tag1.id, tag2.id],
            'time_minutes': 60,
            'price': 5.00
        }

        res = self.client.post(RECIPES_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data['id'])
        tags = recipe.tags.all()
        self.assertEqual(tags.count(), 2)
        self.assertIn(tag1, tags)
        self.assertIn(tag2, tags)

    def test_create_recipe_with_ingredients(self):
        """Test create recipe with tags"""
        ingredient1 = sample_ingredient(user=self.user, name='Meat')
        ingredient2 = sample_ingredient(user=self.user, name='Potato')

        payload = {
            'title': 'Meat Pie',
            'ingredients': [ingredient1.id, ingredient2.id],
            'time_minutes': 90,
            'price': 12.00
        }

        res = self.client.post(RECIPES_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data['id'])
        ingredients = recipe.ingredients.all()
        self.assertEqual(ingredients.count(), 2)
        self.assertIn(ingredient1, ingredients)
        self.assertIn(ingredient2, ingredients)

    def test_partial_updating_recipes(self):
        """Test we can update a partial update"""
        recipe = sample_recipe(user=self.user)
        recipe.tags.add(sample_tag(user=self.user))
        new_tag = sample_tag(user=self.user, name='Curry')

        payload = {'title': 'Chicken Tikka', 'tags': new_tag.id}
        url = detail_url(recipe.id)
        self.client.patch(url, payload)

        recipe.refresh_from_db()

        self.assertEqual(recipe.title, payload['title'])
        tags = recipe.tags.all()
        self.assertEqual(len(tags), 1)
        self.assertIn(new_tag, tags)

    def test_full_updating_recipes(self):
        """Test we can update with a put update"""
        recipe = sample_recipe(user=self.user)
        recipe.tags.add(sample_tag(user=self.user))
        payload = {
            'title': 'Spag Bol',
            'time_minutes': 40,
            'price': 2.50
        }

        url = detail_url(recipe.id)
        self.client.put(url, payload)

        recipe.refresh_from_db()

        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.time_minutes, payload['time_minutes'])
        self.assertEqual(recipe.price, payload['price'])
        tags = recipe.tags.all()
        self.assertEqual(len(tags), 0)


class RecipeImageUploadTests(TestCase):
    """Test recipe image upload"""

    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            'test@example.com',
            'password'
        )
        self.client.force_authenticate(self.user)
        self.recipe = sample_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_uploading_image_to_recipe(self):
        """Test uploading image to recipe"""
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix='.jpg') as ntf:
            img = Image.new('RGB', (10, 10))
            img.save(ntf, format='JPEG')
            ntf.seek(0)
            res = self.client.post(url, {'image': ntf}, format='multipart')

        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('image', res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_uploading_image_bad_request(self):
        """Uploading bad image test"""
        url = image_upload_url(self.recipe.id)
        res = self.client.post(url, {'image': 'notimage'}, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
