%define __python /usr/bin/python%{pybasever}
# sitelib for noarch packages
%{!?python_sitelib: %global python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}
%define pyver 27
%define pybasever 2.7

%define name rdrf
%define version 0.9.3
%define unmangled_version 0.9.3
%define release 1
%define webapps /usr/local/webapps
%define installdir %{webapps}/%{name}
%define buildinstalldir %{buildroot}/%{installdir}
%define settingsdir %{buildinstalldir}/defaultsettings
%define logdir %{buildroot}/var/log/%{name}
%define scratchdir %{buildroot}/var/lib/%{name}/scratch
%define mediadir %{buildroot}/var/lib/%{name}/media
%define staticdir %{buildinstalldir}/static

Summary: rdrf
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{unmangled_version}.tar.gz
License: GNU AGPL v3
Group: Applications/Internet
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: x86_64
Vendor: Centre for Comparative Genomics <web@ccg.murdoch.edu.au>
BuildRequires: python%{pyver}-virtualenv python%{pyver}-devel postgresql94-devel zlib-devel libyaml-devel
Requires: python%{pyver} zlib libyaml postgresql94-libs python%{pyver}-mod_wsgi

%description
Registry rdrf

%prep

if [ -d ${RPM_BUILD_ROOT}%{installdir} ]; then
    echo "Cleaning out stale build directory" 1>&2
    rm -rf ${RPM_BUILD_ROOT}%{installdir}
fi

# Turn off brp-python-bytecompile because it compiles the settings file.
%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

%build
# Nothing, all handled by install

%install
NAME=%{name}

for directory in "%{settingsdir} %{staticdir} %{logdir} %{scratchdir} %{mediadir}"; do
    mkdir -p $directory;
done;

if ! test -e $CCGSOURCEDIR/build-number-.txt; then
    echo '#Generated by spec file' > build-number.txt
    export TZ=Australia/Perth
    DATE=`date`
    echo "build.timestamp=\"$DATE\"" >> build-number.txt
fi
echo "build.user=\"$USER\"" >> build-number.txt
echo "build.host=\"$HOSTNAME\"" >> build-number.txt
cp build-number.txt %{buildinstalldir}/

cd $CCGSOURCEDIR/rdrf

# Create a python prefix with app requirements
mkdir -p %{buildinstalldir}
virtualenv-%{pybasever} %{buildinstalldir}
. %{buildinstalldir}/bin/activate

# Use specific version of pip -- avoids surprises with deprecated
# options, etc.
pip install --force-reinstall --upgrade 'pip>=7.0,<8.0'
pip --version

# The app has a python dependency (HGVS) that specifically pulls in psycopg2
# Make pg_config available on the path so it can build
export PATH=$PATH:/usr/pgsql-9.4/bin

# Install package into the prefix
# hgvs was failing due to lack of nose, hence the order
pip install nose
pip install -r runtime-requirements.txt
pip install .

# Fix up paths in virtualenv, enable use of global site-packages
virtualenv-%{pybasever} --relocatable %{buildinstalldir}
find %{buildinstalldir} -name \*py[co] -exec rm {} \;
find %{buildinstalldir} -name no-global-site-packages.txt -exec rm {} \;
sed -i "s|`readlink -f ${RPM_BUILD_ROOT}`||g" %{buildinstalldir}/bin/*

# Strip out mention of rpm buildroot from the pip install record
find %{buildinstalldir} -name RECORD -exec sed -i -e "s|${RPM_BUILD_ROOT}||" {} \;

# Strip debug syms out of the compiled python modules which are in the
# build root.
find %{buildinstalldir} -name \*.so -exec strip -g {} \;

# don't need a copy of python interpreter in the virtualenv
rm %{buildinstalldir}/bin/python*

# Create symlinks under install directory to real persistent data directories
APP_SETTINGS_FILE=`find %{buildinstalldir} -path "*/%{name}/settings.py" | sed s:^%{buildinstalldir}/::`
APP_PACKAGE_DIR=`dirname ${APP_SETTINGS_FILE}`
VENV_LIB_DIR=$(dirname `dirname ${APP_SETTINGS_FILE}`)

# Create settings symlink so we can run collectstatic with the default settings
touch %{settingsdir}/__init__.py
ln -fsT ../${APP_SETTINGS_FILE} %{settingsdir}/%{name}.py
ln -fsT %{installdir}/defaultsettings %{buildinstalldir}/${VENV_LIB_DIR}/defaultsettings
ln -fsT %{installdir}/static %{buildinstalldir}/${VENV_LIB_DIR}/static

# Create symlinks under install directory to real persistent data directories
ln -fsT /var/log/%{name} %{buildinstalldir}/${VENV_LIB_DIR}/log
ln -fsT /var/lib/%{name}/scratch %{buildinstalldir}/${VENV_LIB_DIR}/scratch
ln -fsT /var/lib/%{name}/media %{buildinstalldir}/${VENV_LIB_DIR}/media

# Install WSGI configuration into httpd/conf.d
install -D ../centos/rdrf/%{name}.ccg %{buildroot}/etc/httpd/conf.d/%{name}.ccg
install -D ../centos/rdrf/django.wsgi %{buildinstalldir}/django.wsgi

# Install prodsettings conf file to /etc, and replace with symlink
install --mode=0640 -D ../centos/rdrf/rdrf.conf.example %{buildroot}/etc/rdrf/rdrf.conf
install --mode=0640 -D rdrf/prodsettings.py %{buildroot}/etc/rdrf/settings.py
ln -sfT /etc/rdrf/settings.py %{buildinstalldir}/${APP_PACKAGE_DIR}/prodsettings.py


# Symlink django admin script
mkdir -p %{buildroot}/%{_bindir}
ln -fsT %{installdir}/bin/%{name}-manage.py %{buildroot}/%{_bindir}/%{name}

%post
rm -rf %{installdir}/static/*
%{name} collectstatic --noinput > /dev/null
# Remove root-owned logged files just created by collectstatic
rm -rf /var/log/%{name}/*
# Touch the wsgi file to get the app reloaded by mod_wsgi
touch %{installdir}/django.wsgi

%preun
if [ "$1" = "0" ]; then
  # Nuke staticfiles if not upgrading
  rm -rf %{installdir}/static/*
fi

%clean
rm -rf %{buildroot}

%files
%defattr(-,apache,apache,-)
/etc/httpd/conf.d/*
%{_bindir}/%{name}
%attr(-,apache,,apache) %{webapps}/%{name}
%attr(-,apache,,apache) /var/log/%{name}
%attr(-,apache,,apache) /var/lib/%{name}

%attr(710,root,apache) /etc/rdrf
%attr(640,root,apache) /etc/rdrf/settings.py
%attr(640,root,apache) /etc/rdrf/rdrf.conf
%config(noreplace) /etc/rdrf/settings.py
%config(noreplace) /etc/rdrf/rdrf.conf


