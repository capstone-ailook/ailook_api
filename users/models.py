from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    gender = models.CharField(max_length=20, blank=True)
    height = models.FloatField(null=True, blank=True)
    weight = models.FloatField(null=True, blank=True)
    age = models.CharField(max_length=20, blank=True)
    nickname = models.CharField(max_length=50, blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class Item(models.Model):
    CATEGORY_CHOICES = [
        ('top', 'Top'),
        ('bottom', 'Bottom'),
        ('shoes', 'Shoes'),
        ('accessory', 'Accessory'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    kind = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.category}) - {self.user.username if self.user else 'Global'}"

class Cody(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='codies')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    tags = models.JSONField(default=list, blank=True)
    
    # Items
    top = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL, related_name='codies_as_top')
    bottom = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL, related_name='codies_as_bottom')
    shoes = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL, related_name='codies_as_shoes')
    accessory = models.ForeignKey(Item, null=True, blank=True, on_delete=models.SET_NULL, related_name='codies_as_accessory')

    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} by {self.user.username}"

class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username}: {self.title or 'New Chat'}"

class ChatMessage(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('ai', 'AI')]
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    text = models.TextField()
    image_url = models.URLField(max_length=500, blank=True)
    # AI 추천 응답의 retrieved outfit 사진들 (D7).
    # 각 항목: {image, image_url, score, substyle, caption_snippet}
    outfits = models.JSONField(default=list, blank=True)
    # 클로젯-탭 추천 시 앵커로 쓰인 사용자 Item (create-cody 슬롯 연결용, D9).
    anchor_item_id = models.IntegerField(null=True, blank=True)
    anchor_category = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.role}] {self.user.username}: {self.text[:40]}"
