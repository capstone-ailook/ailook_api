from rest_framework import serializers
from .models import UserProfile, Item, Cody
from urllib.parse import urlparse

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['gender', 'height', 'weight', 'age', 'nickname']

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'user', 'name', 'category', 'kind', 'description', 'image_url', 'tags', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        image_url = representation.get('image_url')
        if image_url and request:
            parsed = urlparse(image_url)
            if parsed.scheme and parsed.netloc:
                path = parsed.path
                if parsed.query:
                    path += f"?{parsed.query}"
            else:
                path = image_url
            representation['image_url'] = request.build_absolute_uri(path)
        return representation

class CodySerializer(serializers.ModelSerializer):
    top_detail = ItemSerializer(source='top', read_only=True)
    bottom_detail = ItemSerializer(source='bottom', read_only=True)
    shoes_detail = ItemSerializer(source='shoes', read_only=True)
    accessory_detail = ItemSerializer(source='accessory', read_only=True)

    class Meta:
        model = Cody
        fields = [
            'id', 'user', 'name', 'description', 'image_url', 'tags',
            'top', 'top_detail',
            'bottom', 'bottom_detail',
            'shoes', 'shoes_detail',
            'accessory', 'accessory_detail',
            'is_favorite', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get('request')
        image_url = representation.get('image_url')
        if image_url and request:
            parsed = urlparse(image_url)
            if parsed.scheme and parsed.netloc:
                path = parsed.path
                if parsed.query:
                    path += f"?{parsed.query}"
            else:
                path = image_url
            representation['image_url'] = request.build_absolute_uri(path)
        return representation
