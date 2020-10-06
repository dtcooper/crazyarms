from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic.edit import FormView


def index(request):
    if not User.objects.exists():
        return redirect('first-run')
    elif request.user.is_authenticated:
        return render(request, 'base.html', {'title': request.user.username})
    else:
        return redirect('admin:login')


class FirstRunView(FormView):
    template_name = 'first_run.html'
    form_class = UserCreationForm
    success_url = reverse_lazy('index')

    def dispatch(self, request, *args, **kwargs):
        # Only work if no user exists
        if User.objects.exists():
            return redirect('index')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_superuser = True
        user.save()
        login(self.request, user)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({'title': 'Initial Setup', 'hidenav': True})
        return context
